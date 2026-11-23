# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class L10nPtIrsWithholdingTable(models.Model):
    _name = "l10n.pt.irs.withholding.table"
    _description = "IRS Withholding Table"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Official table number (Roman numeral) assigned by the annual "
        "Despacho approving the withholding tables.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
