# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class Company(models.Model):
    _inherit = "res.company"

    moloni_client_id = fields.Char()
    moloni_client_secret = fields.Char()
    moloni_username = fields.Char()
    moloni_password = fields.Char()
    moloni_company_id = fields.Integer(
        "Moloni Company ID",
        help="The company_id identifying this company in the Moloni account.",
    )
    moloni_access_token = fields.Char(readonly=True, groups="base.group_system")
    moloni_refresh_token = fields.Char(readonly=True, groups="base.group_system")
    moloni_token_expires_at = fields.Datetime(readonly=True, groups="base.group_system")
    has_moloni = fields.Boolean(compute="_compute_has_moloni")

    @api.depends(
        "moloni_client_id",
        "moloni_client_secret",
        "moloni_username",
        "moloni_password",
        "moloni_company_id",
    )
    def _compute_has_moloni(self):
        for company in self:
            company.has_moloni = all(
                [
                    company.moloni_client_id,
                    company.moloni_client_secret,
                    company.moloni_username,
                    company.moloni_password,
                    company.moloni_company_id,
                ]
            )
