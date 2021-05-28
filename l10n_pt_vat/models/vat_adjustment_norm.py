# Copyright (C) 2014- Sossia, Lda. (<http://www.sossia.pt>)
# Copyright (C) 2021 Open SOurce Integrators (<http://www.opensourceintegrators.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountVATAdjustmentNorm(models.Model):
    "Support fields 40/41 of the VAT Statement)"

    _name = "account.vat.adjustment_norm"
    _description = "VAT Adjustment Norm"

    name = fields.Char(required=True)
    active = fields.Boolean(
        default=True,
        help="If the active field is set to False, it "
        "will allow you to hide the adjustment norm without removing it.",
    )
    note = fields.Text(string="Description", translate=True)
    out_refunds = fields.Boolean(
        string="Use on company refunds",
        help="If True, it will allow you to apply the adjustment "
        "norm to your company refunds.",
    )
    in_refunds = fields.Boolean(
        string="Use on third party refunds",
        help="If True, it will allow you to apply the adjustment "
        "norm to third party companies refunds.",
    )
    move_type = fields.Selection(
        selection=[
            ("out_refund", "Customer Credit Note"),
            ("in_refund", "Vendor Credit Note"),
        ],
        compute="_compute_move_type",
        store=True,
    )

    @api.depends("out_refunds", "in_refunds")
    def _compute_move_type(self):
        for norm in self:
            if norm.out_refunds:
                norm.move_type = "out_refund"
            elif norm.in_refunds:
                norm.move_type = "in_refund"
            else:
                norm.move_type = False
