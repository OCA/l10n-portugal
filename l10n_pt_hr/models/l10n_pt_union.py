# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class L10nPtUnion(models.Model):
    _name = "l10n.pt.union"
    _description = "Trade Union"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    l10n_pt_dues_rate = fields.Float(
        string="Union Dues Rate (%)",
        help="Percentage of the contributory base used to compute the "
        "union dues (quotizacao sindical) withheld from the worker.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
