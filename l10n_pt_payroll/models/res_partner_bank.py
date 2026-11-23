# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import Command, api, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    @api.model_create_multi
    def create(self, vals_list):
        version_id = self.env.context.get("payroll_bank_account_version_id")
        if not version_id:
            return super().create(vals_list)
        version = self.env["hr.version"].browse(version_id).exists()
        employee = version._get_payroll_bank_account_employee()
        accounts = super().create(
            [
                dict(
                    vals,
                    partner_id=employee.work_contact_id.id,
                    active=True,
                    allow_out_payment=False,
                )
                for vals in vals_list
            ]
        )
        employee.write(
            {"bank_account_ids": [Command.link(account.id) for account in accounts]}
        )
        if self.env.context.get("payroll_select_bank_account"):
            accounts.ensure_one()
            version.payment_bank_account_id = accounts
        return accounts
