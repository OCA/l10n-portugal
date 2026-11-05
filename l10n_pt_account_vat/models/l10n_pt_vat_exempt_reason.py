# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class VatExemptReason(models.Model):
    _name = "account.l10n_pt.vat.exempt.reason"
    _description = "VAT Exemption Reason"
    _order = "code"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    note = fields.Text(string="Description")

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}"
