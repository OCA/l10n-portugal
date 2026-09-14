# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError, ValidationError


class AccountPaymentOrder(models.Model):
    _inherit = "account.payment.order"

    def generate_payment_file(self):
        # EasyPay direct debits are submitted through the API on upload;
        # no file is generated.
        if self.payment_method_id.code == "easypay_direct_debit":
            return (False, False)
        return super().generate_payment_file()

    def open2generated(self):
        result = super().open2generated()
        if self.payment_method_id.code == "easypay_direct_debit":
            # Generate only reserves the debits — the capture POSTs
            # happen on the later Upload request.
            for payment in self.payment_ids.filtered(lambda p: p.state == "draft"):
                payment._easypay_dd_reserve_capture()
        return result

    def generated2uploaded(self):
        # Submitting the reserved debits to EasyPay is what 'File
        # Successfully Uploaded' means for this method; payments are then
        # posted and reconciled as usual.
        if self.payment_method_id.code == "easypay_direct_debit":
            self.ensure_one()
            if self.state == "uploaded":
                return True
            if self.state != "generated":
                raise UserError(
                    _(
                        "EasyPay direct debits can only be uploaded after "
                        "the payment order has been generated. Generate "
                        "the order first."
                    )
                )
            self._easypay_submit_captures()
        return super().generated2uploaded()

    def action_cancel(self):
        self._easypay_dd_check_reserved_orders()
        return super().action_cancel()

    def draft2open(self):
        self._easypay_dd_check_reserved_orders()
        return super().draft2open()

    def unlink(self):
        self._easypay_dd_check_reserved_orders()
        return super().unlink()

    def _easypay_dd_check_reserved_orders(self):
        """Refuse flows that could discard unresolved EasyPay debits."""
        for order in self:
            reserved = order.payment_ids.mapped("easypay_dd_transaction_ids").filtered(
                "_easypay_is_direct_debit"
            )
            if reserved:
                raise UserError(
                    _(
                        "Payment order %(order)s has %(count)s EasyPay "
                        "direct debit(s) that may already have reached "
                        "EasyPay. Reconcile them before cancelling or "
                        "deleting this order.",
                        order=order.name or order.id,
                        count=len(reserved),
                    )
                )

    def _easypay_submit_captures(self):
        """Submit the debits reserved at Generate time to EasyPay.

        Every payment must carry exactly one Direct Debit reservation;
        anything else means the order was not generated properly and no
        capture may be sent. Provider rejections are aggregated so the
        operator sees every failed debit at once; unexpected errors
        propagate so the whole upload rolls back.
        """
        self.ensure_one()
        for payment in self.payment_ids:
            reservations = payment.easypay_dd_transaction_ids
            if (
                payment.state != "draft"
                or len(reservations) != 1
                or not reservations._easypay_is_direct_debit()
            ):
                raise UserError(
                    _(
                        "Payment order %(order)s cannot be uploaded: "
                        "payment %(payment)s has no single pending EasyPay "
                        "reservation. Generate the order to create them.",
                        order=self.name or self.id,
                        payment=payment.payment_reference or payment.id,
                    )
                )
        errors = []
        for payment in self.payment_ids:
            try:
                payment._easypay_submit_capture(payment.easypay_dd_transaction_ids)
            except (UserError, ValidationError) as e:
                errors.append(f"• {payment.payment_reference or payment.id}: {e}")
        if errors:
            raise UserError(
                _(
                    "Some direct debits could not be submitted to EasyPay:\n"
                    "%(errors)s\n\n"
                    "Review the issues before trying again. Retries reuse the "
                    "original EasyPay request within its submission window.",
                    errors="\n".join(errors),
                )
            )
