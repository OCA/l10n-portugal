# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# Copyright (C) 2026 Odoo S.A.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models

# Region/category selections mirror l10n_pt_certification
# (Odoo WIP, PR odoo/odoo#196102); drop when the core module lands.
L10N_PT_TAX_REGIONS = [
    ("PT-ALL", "All Regions"),
    ("PT", "Mainland Portugal"),
    ("PT-MA", "Madeira"),
    ("PT-AC", "Azores"),
]

L10N_PT_TAX_CATEGORIES = [
    ("N", "Normal"),
    ("I", "Intermediate"),
    ("R", "Reduced"),
    ("E", "Exempt"),
]

# Standard PT rates uniquely identify region and SAF-T tax category.
# Used to seed tax groups, both on install and on migration.
L10N_PT_RATE_MAP = {
    0: ("PT-ALL", "E"),
    4: ("PT-AC", "R"),
    5: ("PT-MA", "R"),
    6: ("PT", "R"),
    9: ("PT-AC", "I"),
    12: ("PT-MA", "I"),
    13: ("PT", "I"),
    16: ("PT-AC", "N"),
    22: ("PT-MA", "N"),
    23: ("PT", "N"),
}


class AccountTaxGroup(models.Model):
    _inherit = "account.tax.group"

    l10n_pt_tax_region = fields.Selection(
        selection=L10N_PT_TAX_REGIONS,
        string="Region (PT)",
        default="PT",
    )
    l10n_pt_tax_category = fields.Selection(
        selection=L10N_PT_TAX_CATEGORIES,
        string="Tax Category (PT)",
        default="N",
    )
