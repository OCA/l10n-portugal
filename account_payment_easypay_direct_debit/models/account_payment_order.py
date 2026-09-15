# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError


class AccountPaymentOrder(models.Model):
    _inherit = "account.payment.order"

    def generate_payment_file(self):
        # EasyPay direct debits are submitted through the API on upload;
        # no file is generated.
        if self.payment_method_id.code == "easypay_direct_debit":
            return (False, False)
        return super().generate_payment_file()

    def generated2uploaded(self):
        # Submitting the debits to EasyPay is what 'File Successfully
        # Uploaded' means for this method; payments are then posted and
        # reconciled as usual.
        if self.payment_method_id.code == "easypay_direct_debit":
            self._easypay_submit_captures()
        return super().generated2uploaded()

    def _easypay_submit_captures(self):
        """Submit one EasyPay capture per draft payment of this order.

        Payments already submitted (a non-final payment.transaction
        exists) are skipped, making a retry after partial failure safe.
        A transaction stuck in 'draft' also blocks resubmission — the
        capture may have reached EasyPay without being tracked.
        Resubmissions are additionally safe at the API level: every
        capture is sent with an Idempotency-Key derived from the
        deterministic transaction key, so EasyPay replays the original
        response instead of debiting twice.
        """
        self.ensure_one()
        errors = []
        for payment in self.payment_ids.filtered(lambda p: p.state == "draft"):
            if payment.easypay_dd_transaction_ids.filtered(
                lambda t: t.state in ("draft", "pending", "authorized", "done")
            ):
                continue
            try:
                payment._easypay_submit_capture()
            except Exception as e:
                errors.append(f"• {payment.payment_reference or payment.id}: {e}")
        if errors:
            raise UserError(
                _(
                    "Some direct debits could not be submitted to EasyPay:\n"
                    "%(errors)s\n\nFix the issues and mark the order as "
                    "uploaded again — already submitted debits are not "
                    "resent.",
                    errors="\n".join(errors),
                )
            )
