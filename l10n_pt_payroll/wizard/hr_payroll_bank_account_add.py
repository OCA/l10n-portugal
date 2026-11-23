# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import Command, fields, models
from odoo.exceptions import UserError


class HrPayrollBankAccountAdd(models.TransientModel):
    _name = "hr.payroll.bank.account.add"
    _description = "Add Bank Account"

    version_id = fields.Many2one(
        "hr.version", required=True, readonly=True, ondelete="cascade"
    )
    acc_number = fields.Char(string="Account Number", required=True)

    def action_add_bank_account(self):
        self.ensure_one()
        self.check_access("write")
        version = self.version_id
        employee = version._get_payroll_bank_account_employee()
        if not self.acc_number or not self.acc_number.strip():
            raise UserError(self.env._("Enter a bank account number."))
        account = (
            self.env["res.partner.bank"]
            .with_context(payroll_bank_account_version_id=False)
            .create(self._prepare_res_partner_bank_values(employee))
        )
        employee.write({"bank_account_ids": [Command.link(account.id)]})
        version.write({"payment_bank_account_id": account.id})
        return {"type": "ir.actions.client", "tag": "soft_reload"}

    def _prepare_res_partner_bank_values(self, employee):
        return {
            "partner_id": employee.work_contact_id.id,
            "acc_number": self.acc_number.strip(),
            "allow_out_payment": False,
        }
