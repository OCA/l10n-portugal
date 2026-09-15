# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    """Track EasyPay direct debit captures as offline payment transactions.

    One transaction per capture submitted to EasyPay from a payment order:
    ``operation='offline'`` marks the merchant-initiated debit, the capture
    ID is stored in ``easypay_transaction_id``, and the ``reference`` is the
    transaction key echoed back by webhook notifications — so the standard
    EasyPay webhook flow matches these transactions automatically.
    """

    _inherit = "payment.transaction"

    mandate_id = fields.Many2one(
        comodel_name="account.banking.mandate",
        string="Mandate",
        readonly=True,
    )
    payment_order_id = fields.Many2one(
        related="payment_id.payment_order_id",
        string="Payment Order",
        store=True,
        index=True,
    )

    def _easypay_is_direct_debit(self):
        """Whether this transaction is an EasyPay direct debit capture.

        ``operation='offline'`` alone is not enough: tokenized card/MBWay
        charges via ``_send_payment_request`` use it too — only debits
        submitted from a payment order carry a ``mandate_id``.
        """
        return (
            self.provider_code == "easypay"
            and self.operation == "offline"
            and bool(self.mandate_id)
        )

    @staticmethod
    def _easypay_dd_state_for_status(status):
        """Map an EasyPay capture status to a transaction state, or False."""
        if status in ("paid", "captured", "complete", "success"):
            return "done"
        if status in ("pending", "waiting", "authorized", "authorised"):
            return "pending"
        if status in (
            "cancelled",
            "canceled",
            "rejected",
            "refused",
            "returned",
            "chargeback",
            "bounced",
        ):
            return "cancel"
        if status in ("failed", "error"):
            return "error"
        return False

    @staticmethod
    def _easypay_dd_extract_status(data):
        """Pull the capture status out of an EasyPay API response."""
        return data.get("status") or (data.get("payment") or {}).get("status")

    def _apply_payment_state(self, status, notification_data):
        # DD statuses (rejected, returned, ...) are not covered by the
        # checkout mapping; drive those transitions from the DD map.
        dd_txs = self.filtered(lambda t: t._easypay_is_direct_debit())
        dd_txs._easypay_dd_apply_status(status, notification_data)
        remaining = self - dd_txs
        if remaining:
            return super(PaymentTransaction, remaining)._apply_payment_state(
                status, notification_data
            )

    def _easypay_dd_apply_status(self, status, notification_data):
        """Apply an EasyPay capture status; unknown statuses are ignored."""
        new_state = self._easypay_dd_state_for_status(status)
        if not new_state:
            return
        message = notification_data.get("message")
        if isinstance(message, list):
            message = ", ".join(str(m) for m in message)
        for tx in self:
            if new_state == "done":
                tx._set_done(extra_allowed_states=("cancel", "error"))
            elif new_state == "cancel":
                tx._set_canceled(
                    state_message=message, extra_allowed_states=("done", "error")
                )
            elif new_state == "error":
                tx._set_error(
                    message or _("EasyPay direct debit failed"),
                    extra_allowed_states=("cancel",),
                )
            elif new_state == "pending":
                tx._set_pending(extra_allowed_states=("cancel", "error"))

    def _post_process(self):
        dd_txs = self.filtered(lambda t: t._easypay_is_direct_debit())
        for tx in dd_txs:
            # Skip the account_payment post-processing: its cancel branch
            # calls action_cancel(), which fails on reconciled payments.
            # Rejected debits keep the posted payment — the accountant
            # reverses it manually after checking the bank statement.
            # Draft/pending debits are left unprocessed so the failure
            # notification can still fire when they reach a final state.
            if tx.state in ("cancel", "error"):
                tx.is_post_processed = True
                tx._easypay_dd_notify_failure()
            elif tx.state in ("done", "authorized"):
                tx.is_post_processed = True
        remaining = self - dd_txs
        if remaining:
            return super(PaymentTransaction, remaining)._post_process()

    def _easypay_dd_notify_failure(self):
        """Create an activity on the payment order for rejected debits."""
        self.ensure_one()
        order = self.payment_order_id
        if not order:
            return
        order.activity_schedule(
            "mail.mail_activity_data_warning",
            user_id=(order.generated_user_id or order.create_uid or self.env.user).id,
            note=_(
                "EasyPay direct debit %(key)s for payment %(payment)s "
                "(%(partner)s) ended in state '%(state)s'. The payment was "
                "already posted — reverse it manually if the debit did not "
                "settle.",
                key=self.reference,
                payment=self.payment_id.payment_reference or self.payment_id.id,
                partner=self.partner_id.display_name,
                state=self.state,
            ),
        )

    def _log_message_on_linked_documents(self, message):
        res = super()._log_message_on_linked_documents(message)
        # Mirror transaction status messages on the payment order's chatter.
        if self.payment_order_id:
            self.payment_order_id.message_post(body=message)
        return res

    @api.model
    def _easypay_dd_cron_sync_pending(self):
        """Poll EasyPay for the status of aged pending direct debits."""
        min_age_hours = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("account_payment_easypay_direct_debit.poll_min_age_hours", 1)
        )
        limit = fields.Datetime.now() - timedelta(hours=min_age_hours)
        pending = self.search(
            [
                ("provider_code", "=", "easypay"),
                ("operation", "=", "offline"),
                ("state", "=", "pending"),
                ("easypay_transaction_id", "!=", False),
                ("create_date", "<", limit),
            ]
        )
        for tx in pending:
            tx._easypay_dd_sync_from_api()

    def _easypay_dd_sync_from_api(self):
        """Fetch the capture status from EasyPay and apply it."""
        self.ensure_one()
        if not self.easypay_transaction_id:
            return
        try:
            data = self.provider_id._easypay_make_request(
                f"/2.0/capture/{self.easypay_transaction_id}", method="GET"
            )
        except Exception:
            _logger.exception(
                "EasyPay status sync failed for transaction %s", self.reference
            )
            return
        self._apply_payment_state(self._easypay_dd_extract_status(data), data)
        self.easypay_payment_details = data
