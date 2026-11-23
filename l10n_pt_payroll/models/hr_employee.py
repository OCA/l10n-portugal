# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models
from odoo.exceptions import AccessError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # IRS withholding determinants are version fields; expose them on
    # the employee through delegation so the form edits the current
    # version.
    l10n_pt_irs_family_status = fields.Selection(
        related="version_id.l10n_pt_irs_family_status",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_dependents = fields.Integer(
        related="version_id.l10n_pt_irs_dependents",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_disabled_dependents = fields.Integer(
        related="version_id.l10n_pt_irs_disabled_dependents",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_disabled_dep_factor = fields.Integer(
        related="version_id.l10n_pt_irs_disabled_dep_factor",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_spouse_disabled = fields.Boolean(
        related="version_id.l10n_pt_irs_spouse_disabled",
        readonly=False,
        inherited=True,
    )
    l10n_pt_military_disabled = fields.Boolean(
        related="version_id.l10n_pt_military_disabled",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_region = fields.Selection(
        related="version_id.l10n_pt_irs_region",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_pensioner = fields.Boolean(
        related="version_id.l10n_pt_irs_pensioner",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_non_resident = fields.Boolean(
        related="version_id.l10n_pt_irs_non_resident",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_single_payer_declared = fields.Boolean(
        related="version_id.l10n_pt_irs_single_payer_declared",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_preferred_rate = fields.Float(
        related="version_id.l10n_pt_irs_preferred_rate",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_jovem = fields.Boolean(
        related="version_id.l10n_pt_irs_jovem",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_income_years = fields.Integer(
        related="version_id.l10n_pt_irs_income_years",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_table_id = fields.Many2one(
        related="version_id.l10n_pt_irs_table_id",
        inherited=True,
    )
    l10n_pt_payment_method = fields.Selection(
        related="version_id.l10n_pt_payment_method",
        readonly=False,
        inherited=True,
        groups="hr.group_hr_manager",
    )
    payment_method_id = fields.Many2one(
        related="version_id.payment_method_id",
        inherited=True,
        readonly=False,
        related_sudo=False,
        groups="hr.group_hr_manager",
    )
    payment_bank_account_id = fields.Many2one(
        related="version_id.payment_bank_account_id",
        inherited=True,
        readonly=False,
        related_sudo=False,
        groups="hr.group_hr_manager",
    )

    def action_add_payment_bank_account(self):
        self.ensure_one()
        self.check_access("write")
        if not self.env.user.has_group("hr.group_hr_manager"):
            raise AccessError(self.env._("Only HR managers can add bank accounts."))
        version = self.version_id
        employee = version._get_payroll_bank_account_employee()
        return {
            "name": self.env._("Add Bank Account"),
            "type": "ir.actions.act_window",
            "res_model": "res.partner.bank",
            "views": [
                (
                    self.env.ref("l10n_pt_payroll.view_payroll_partner_bank_form").id,
                    "form",
                )
            ],
            "target": "new",
            "context": {
                "default_partner_id": employee.work_contact_id.id,
                "payroll_bank_account_version_id": version.id,
                "payroll_select_bank_account": True,
            },
        }
