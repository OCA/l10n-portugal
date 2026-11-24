# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import hashlib
from datetime import timedelta

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

    def _easypay_submit_capture(self, tx):
        """Submit a reserved direct debit capture to EasyPay.

        ``tx`` is the reservation created at Generate time; its frozen
        reference, amount and description are what EasyPay receives.
        """
        self.ensure_one()
        self.check_access("write")
        tx.ensure_one()
        tx.check_access("write")
        tx._easypay_lock_operation()
        tx.invalidate_recordset()
        provider = tx.provider_id
        mandate = tx.mandate_id
        mandate.check_access("read")
        order_provider = self.payment_order_id.payment_mode_id._easypay_get_provider()
        if (
            provider != order_provider
            or mandate != self.mandate_id
            or mandate.easypay_frequent_id != tx.provider_reference
            or tx.currency_id != self.currency_id
            or tx.currency_id.compare_amounts(tx.amount, self.amount)
        ):
            raise UserError(
                _(
                    "The reserved EasyPay debit %(reference)s no longer "
                    "matches payment %(payment)s. Reconcile the original "
                    "debit before retrying.",
                    reference=tx.reference,
                    payment=self.payment_reference or self.id,
                )
            )
        if tx.easypay_transaction_id:
            if tx.state in ("pending", "authorized", "done"):
                return
            raise UserError(
                _(
                    "EasyPay capture for %s requires reconciliation " "before upload.",
                    tx.reference,
                )
            )
        if tx.state != "draft":
            raise UserError(
                _(
                    "EasyPay debit %s requires reconciliation before upload.",
                    tx.reference,
                )
            )
        if (
            mandate.state != "valid"
            or mandate.format != "easypay"
            or mandate.easypay_provider_id != provider
            or mandate.partner_id.commercial_partner_id
            != self.partner_id.commercial_partner_id
        ):
            raise UserError(
                _(
                    "EasyPay debit %(reference)s cannot be submitted: "
                    "mandate %(mandate)s is not valid for this partner.",
                    reference=tx.reference,
                    mandate=mandate.display_name,
                )
            )
        self._easypay_dd_check_submission_deadline(tx)
        mandate._easypay_refresh_state(provider)
        self._easypay_dd_check_submission_deadline(tx)
        # Idempotent submission: a retry resends the same key and EasyPay
        # replays the original response instead of debiting twice. Hashed
        # to stay within the 50-char limit.
        idempotency_key = hashlib.sha256(tx.reference.encode()).hexdigest()[:50]
        # sudo: easypay_api_key is restricted to base.group_system; the
        # provider identity was validated by the mandate refresh above.
        response = provider.sudo()._easypay_make_request(
            f"/2.0/capture/{tx.provider_reference}",
            {
                "descriptive": tx.easypay_dd_description or "",
                "transaction_key": tx.reference,
                "value": tx.amount,
            },
            idempotency_key=idempotency_key,
        )
        provider._easypay_raise_for_status(response, "direct debit")
        capture_id = response.get("id")
        if not isinstance(capture_id, str) or not capture_id.strip():
            raise UserError(
                _(
                    "EasyPay accepted the direct debit for payment "
                    "%(name)s but returned no capture ID — the debit "
                    "cannot be tracked. Check EasyPay before retrying.",
                    name=self.payment_reference or self.id,
                )
            )
        tx.write(
            {
                "easypay_transaction_id": capture_id,
                "easypay_payment_details": response,
            }
        )
        # A successful submission acknowledges receipt, not settlement.
        tx._set_pending(extra_allowed_states=("cancel", "error"))

    def _easypay_dd_check_submission_deadline(self, tx):
        """Refuse submission once the armed window has expired."""
        self.ensure_one()
        tx.ensure_one()
        prepared_at = self.payment_order_id.easypay_dd_prepared_at
        if not prepared_at or fields.Datetime.now() >= prepared_at + timedelta(
            hours=23
        ):
            raise UserError(
                _(
                    "The EasyPay submission window has expired for %s. "
                    "Reconcile the original debit before retrying.",
                    tx.reference,
                )
            )

    def _easypay_dd_reserve_capture(self):
        """Reserve this payment's direct debit without submitting it.

        Called by the Generate step: freezes the provider, mandate,
        amount and descriptive payload on a draft transaction so the
        later Upload step submits exactly what was reserved.
        """
        self.ensure_one()
        self.check_access("write")
        provider = self.payment_order_id.payment_mode_id._easypay_get_provider()
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
        if (
            mandate.state != "valid"
            or mandate.format != "easypay"
            or mandate.easypay_provider_id != provider
            or mandate.partner_id.commercial_partner_id
            != self.partner_id.commercial_partner_id
        ):
            raise UserError(
                _(
                    "Payment %(name)s cannot reserve an EasyPay debit: "
                    "mandate %(mandate)s is not valid for this partner.",
                    name=self.payment_reference or self.id,
                    mandate=mandate.display_name,
                )
            )
        reserved = self.easypay_dd_transaction_ids
        if reserved:
            return reserved
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
                "provider_reference": mandate.easypay_frequent_id,
                "easypay_dd_description": (
                    self.payment_reference or self.payment_order_id.name or ""
                )[:140],
            }
        )

    def _easypay_transaction_key(self):
        """Return a unique key identifying this debit at EasyPay."""
        self.ensure_one()
        line_name = self.payment_line_ids[:1].name
        return f"{line_name or self.payment_order_id.name}-{self.id}"
