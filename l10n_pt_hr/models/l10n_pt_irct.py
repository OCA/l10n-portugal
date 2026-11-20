# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class L10nPtIrct(models.Model):
    _name = "l10n.pt.irct"
    _description = "Collective Agreement (IRCT)"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        help="Official reference of the agreement, e.g. the BTE publication "
        "number or CCT code."
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
