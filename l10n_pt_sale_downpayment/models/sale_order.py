# Copyright (C) 2023 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _create_invoices(self, grouped=False, final=False, date=None):
        moves = super()._create_invoices(grouped=grouped, final=final, date=date)
        moves_downp = moves.filtered(lambda x: x.line_ids.filtered("is_downpayment"))
        reverts = self.env["account.move"]
        for move_dp in moves_downp:
            revert_dp = move_dp.copy()
            reverts |= revert_dp
            move_lines_to_unlink = move_dp.invoice_line_ids.filtered(
                lambda x: x.is_downpayment and x.price_subtotal < 0
            )
            move_lines_to_unlink.unlink()
            revert_lines_to_unlink = revert_dp.invoice_line_ids.filtered(
                lambda x: not (x.is_downpayment and x.price_subtotal < 0)
            )
            revert_lines_to_unlink.unlink()
            # Keep link with Sale Order
            so_lines = move_dp.invoice_line_ids.sale_line_ids
            for line in revert_dp.invoice_line_ids:
                line.sale_line_ids |= so_lines
        return moves
