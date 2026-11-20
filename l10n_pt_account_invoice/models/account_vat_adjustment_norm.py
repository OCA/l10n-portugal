# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class L10nPtVatAdjustmentNorm(models.Model):
    _name = "l10n.pt.vat.adjustment.norm"
    _description = "VAT Adjustment Legal Basis"
    _order = "name, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    note = fields.Text(translate=True)
    out_refunds = fields.Boolean(string="Customer Credit Notes")
    in_refunds = fields.Boolean(string="Vendor Credit Notes")
