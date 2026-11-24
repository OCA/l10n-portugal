# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountPaymentOrder(models.Model):
    _inherit = "account.payment.order"

    easypay_dd_prepared_at = fields.Datetime(readonly=True, copy=False)
    easypay_dd_is_order = fields.Boolean(compute="_compute_easypay_dd_is_order")

    @api.depends("payment_method_id.code")
    def _compute_easypay_dd_is_order(self):
        for order in self:
            order.easypay_dd_is_order = (
                order.payment_method_id.code == "easypay_direct_debit"
            )

    def _easypay_dd_lock_order(self):
        """Serialize EasyPay prepare/upload/destructive flows per order."""
        self.ensure_one()
        self.env.cr.execute(
            "SELECT id FROM account_payment_order WHERE id = %s FOR UPDATE",
            [self.id],
        )

    def action_easypay_prepare_upload(self):
        """Arm this generated order: start the EasyPay submission window."""
        self.ensure_one()
        self.check_access("write")
        self._easypay_dd_lock_order()
        self.invalidate_recordset()
        if not self.easypay_dd_is_order:
            raise UserError(
                _("Only EasyPay direct debit payment orders can be prepared.")
            )
        if self.state != "generated":
            raise UserError(
                _(
                    "EasyPay direct debits can only be prepared after the "
                    "payment order has been generated. Generate the order "
                    "first."
                )
            )
        self._easypay_dd_check_upload_reservations()
        if not self.easypay_dd_prepared_at:
            # Bypass the write guard: only this action sets the timestamp.
            super().write({"easypay_dd_prepared_at": fields.Datetime.now()})
        return True

    def write(self, vals):
        if "easypay_dd_prepared_at" in vals:
            raise UserError(
                _(
                    "The EasyPay upload preparation can only be set by "
                    "'Prepare EasyPay Upload'."
                )
            )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "easypay_dd_prepared_at" in vals:
                raise UserError(
                    _(
                        "The EasyPay upload preparation can only be set by "
                        "'Prepare EasyPay Upload'."
                    )
                )
        return super().create(vals_list)

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
            self._easypay_dd_lock_order()
            self.invalidate_recordset()
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
            if not self.easypay_dd_prepared_at:
                raise UserError(
                    _(
                        "EasyPay direct debits must be prepared for upload "
                        "first. Use 'Prepare EasyPay Upload'."
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

    def cancel2draft(self):
        self._easypay_dd_check_reserved_orders()
        return super().cancel2draft()

    def unlink(self):
        self._easypay_dd_check_reserved_orders()
        return super().unlink()

    def _easypay_dd_check_reserved_orders(self):
        """Refuse flows that could discard protected EasyPay debits.

        Only prepared orders or reservations EasyPay already acknowledged
        are protected; unprepared reservations without a capture ID may
        stay behind for audit — their payment link is released when the
        draft payments are removed.
        """
        for order in self:
            reservations = order.payment_ids.mapped(
                "easypay_dd_transaction_ids"
            ).filtered(lambda t: t._easypay_is_direct_debit())
            if not order.easypay_dd_is_order and not reservations:
                continue
            order._easypay_dd_lock_order()
            order.invalidate_recordset()
            acknowledged = (
                order.payment_ids.mapped("easypay_dd_transaction_ids")
                .filtered(lambda t: t._easypay_is_direct_debit())
                .filtered("easypay_transaction_id")
            )
            if order.easypay_dd_prepared_at or acknowledged:
                raise UserError(
                    _(
                        "Payment order %(order)s has EasyPay direct debit(s) "
                        "that may already have reached EasyPay. Reconcile "
                        "them before cancelling or deleting this order.",
                        order=order.name or order.id,
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
        self.check_access("write")
        self._easypay_dd_check_upload_reservations()
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

    def _easypay_dd_check_upload_reservations(self):
        """Require exactly one Direct Debit reservation per draft payment."""
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
