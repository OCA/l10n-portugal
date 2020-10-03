# Copyright (C) 2014- Sossia, Lda. (<http://www.sossia.pt>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openerp import models, fields


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
