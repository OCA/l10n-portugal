# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    use_invoicexpress = fields.Boolean(
        default=True,
        help="Invoicexpress service is only used if checked."
        " Only relevant for Sales journals.",
    )
