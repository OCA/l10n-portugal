# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class Country(models.Model):
    _inherit = "res.country"

    invoicexpress_name = fields.Char()
