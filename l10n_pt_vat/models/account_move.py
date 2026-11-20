# Copyright (C) 2014 Sossia, Lda. (<http://www.sossia.pt>)
# Copyright (C) 2021 Open SOurce Integrators (<http://www.opensourceintegrators.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    vat_adjustment_norm_id = fields.Many2one(
        "account.vat.adjustment_norm",
        string="VAT Adjustment Norm",
        ondelete="restrict",
        help="Fields 40/41 of the VAT Statement",
    )
    l10npt_vat_exempt_reason = fields.Many2one(
        "account.l10n_pt.vat.exempt.reason",
        string="VAT Exempt Reason",
        readonly=True,
        copy=False,
    )
