# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    easypay_dd_transaction_ids = fields.One2many(
        comodel_name="payment.transaction",
        inverse_name="payment_id",
        string="EasyPay Transactions",
        readonly=True,
    )
    easypay_dd_transaction_count = fields.Integer(
        compute="_compute_easypay_dd_transaction_count"
    )

    @api.depends("easypay_dd_transaction_ids")
    def _compute_easypay_dd_transaction_count(self):
        for payment in self:
            payment.easypay_dd_transaction_count = len(
                payment.easypay_dd_transaction_ids
            )

    def action_view_easypay_dd_transactions(self):
        """Stat button: open this payment's EasyPay transactions only."""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account_payment_easypay_direct_debit.action_easypay_transaction"
        )
        action["domain"] = [("id", "in", self.easypay_dd_transaction_ids.ids)]
        return action

    def _easypay_submit_capture(self):
        """Submit this payment as a SEPA Direct Debit capture to EasyPay.

        Creates the ``payment.transaction`` (``operation='offline'``) that
        the EasyPay webhooks and the polling cron use to track the debit.
        """
        self.ensure_one()
        order = self.payment_order_id
        provider = order.payment_mode_id._easypay_get_provider()
        mandate = self.mandate_id
        if not mandate or not mandate.easypay_frequent_id:
            raise UserError(
                _(
                    "Payment %(name)s has no EasyPay-registered mandate. "
                    "Validate an EasyPay mandate for partner '%(partner)s' "
                    "first.",
                    name=self.payment_reference or self.id,
                    partner=self.partner_id.display_name,
                )
            )
        if mandate.easypay_mandate_state != "active":
            mandate._easypay_refresh_state(provider)
        tx = self._easypay_dd_get_or_create_tx(provider, mandate)
        try:
            # Idempotent submission: a retry after a rollback resends the
            # same key and EasyPay replays the original response instead of
            # debiting twice. Hashed to stay within the 50-char limit.
            idempotency_key = hashlib.sha256(tx.reference.encode()).hexdigest()[:50]
            response = provider._easypay_make_request(
                f"/2.0/capture/{mandate.easypay_frequent_id}",
                {
                    "descriptive": (self.payment_reference or order.name or "")[:140],
                    "transaction_key": tx.reference,
                    "value": self.amount,
                },
                idempotency_key=idempotency_key,
            )
            provider._easypay_raise_for_status(response, "direct debit")
            capture_id = response.get("id")
            if not capture_id:
                raise UserError(
                    _(
                        "EasyPay accepted the direct debit for payment "
                        "%(name)s but returned no capture ID — the debit "
                        "cannot be tracked. Check EasyPay before retrying.",
                        name=self.payment_reference or self.id,
                    )
                )
        except Exception as e:
            tx._set_error(str(e))
            raise
        tx.write(
            {
                "provider_reference": capture_id,
                "easypay_transaction_id": capture_id,
                "easypay_payment_details": response,
            }
        )
        tx._apply_payment_state(response.get("status"), response)
        if tx.state in ("draft", "cancel", "error"):
            # The API envelope's 'ok' is just an ack — the debit is pending
            # until a webhook or the polling cron reports a final status.
            tx._set_pending(extra_allowed_states=("cancel", "error"))

    def _easypay_dd_get_or_create_tx(self, provider, mandate):
        """Return the transaction tracking this payment's direct debit.

        A previously failed transaction is reused so the retry resends
        the same deterministic transaction key — letting EasyPay
        deduplicate it and avoiding a second record for the same debit.
        """
        self.ensure_one()
        failed = self.easypay_dd_transaction_ids.filtered(
            lambda t: t.state in ("cancel", "error")
        )[:1]
        if failed:
            return failed
        return self.env["payment.transaction"].create(
            {
                "reference": self._easypay_transaction_key(),
                "provider_id": provider.id,
                "payment_method_id": self.env.ref(
                    "payment_easypay_oca.payment_method_easypay_direct_debit"
                ).id,
                "partner_id": self.partner_id.id,
                "amount": self.amount,
                "currency_id": self.currency_id.id,
                "operation": "offline",
                "payment_id": self.id,
                "mandate_id": mandate.id,
                "token_id": mandate.easypay_token_id.id,
            }
        )

    def _easypay_transaction_key(self):
        """Return a unique key identifying this debit at EasyPay."""
        self.ensure_one()
        line_name = self.payment_line_ids[:1].name
        return f"{line_name or self.payment_order_id.name}-{self.id}"
