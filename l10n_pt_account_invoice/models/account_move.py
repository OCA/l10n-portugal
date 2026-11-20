# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_pt_vat_adjustment_norm_id = fields.Many2one(
        "l10n.pt.vat.adjustment.norm",
        string="VAT Adjustment Legal Basis",
        ondelete="restrict",
        copy=False,
    )
    l10n_pt_vat_adjustment_norm_note = fields.Text(
        related="l10n_pt_vat_adjustment_norm_id.note"
    )
