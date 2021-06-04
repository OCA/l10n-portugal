# Copyright (C) 2021 Open SOurce Integrators (<http://www.opensourceintegrators.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10npt_vat_exempt_reason = fields.Many2one(
        "account.l10n_pt.vat.exempt.reason", string="VAT Exempt Reason"
    )
