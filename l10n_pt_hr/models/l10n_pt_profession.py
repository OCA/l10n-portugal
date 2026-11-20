# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class L10nPtProfession(models.Model):
    _name = "l10n.pt.profession"
    _description = "Profession (CPP/2010)"
    _order = "code, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Official CPP/2010 code, reported in the Relatório Único (Tabela 16).",
    )
    active = fields.Boolean(default=True)
