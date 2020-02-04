# Copyright (C) 2014- Sossia, Lda. (<http://www.sossia.pt>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models, fields


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    vat_adjustment_norm_id = fields.Many2one(
        "account.vat.adjustment_norm",
        string="VAT Adjustment Norm",
        ondelete="restrict",
        help="Fields 40/41 of the VAT Statement",
    )
