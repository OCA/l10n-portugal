# Copyright (C) 2021 Open SOurce Integrators (<http://www.opensourceintegrators.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_pt_fiscal_zone = fields.Selection(
        [("PT", "Portugal Continental"), ("PT-AC", "Açores"), ("PT-MA", "Madeira")],
        string="Fiscal Zone",
    )
