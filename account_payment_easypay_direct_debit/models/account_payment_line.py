# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountPaymentLine(models.Model):
    _inherit = "account.payment.line"

    @api.model
    def _get_payment_line_grouping_fields(self):
        # Group payment lines by mandate so each generated account.payment
        # maps to a single EasyPay direct debit.
        res = super()._get_payment_line_grouping_fields()
        if "mandate_id" not in res:
            res.append("mandate_id")
        return res
