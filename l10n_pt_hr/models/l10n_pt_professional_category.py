# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class L10nPtProfessionalCategory(models.Model):
    _name = "l10n.pt.professional.category"
    _description = "Professional Category"
    _order = "irct_id, sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    irct_id = fields.Many2one(
        "l10n.pt.collective.contract",
        string="Collective Contract",
        index=True,
        help="Collective agreement defining this category. Leave empty for "
        "categories that apply across agreements.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
