# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    l10n_pt_irs_taxable = fields.Float(
        string="IRS Taxable Share",
        default=0.0,
        help="Share of the rule total that enters the taxable "
        "remuneration R used by the Portuguese IRS retention "
        "computation: 1.0 means fully taxable, 0.5 half, 0.0 exempt. "
        "Use it for partially taxable payments such as the taxable "
        "portion of allowances.",
    )
    l10n_pt_dmr_code = fields.Char(
        string="DMR-AT Income Code",
        help="Income code for the Autoridade Tributaria declaration. "
        "This is independent of the Social Security remuneration nature.",
    )
    l10n_pt_dmr_at_role = fields.Selection(
        selection=[
            ("income", "Income"),
            ("withholding", "IRS Withholding"),
            ("contribution", "Mandatory Contribution"),
            ("union_dues", "Union Dues"),
            ("ignore", "Not Reported"),
        ],
        string="DMR-AT Role",
    )
    l10n_pt_dmr_at_recipient_nipc = fields.Char(
        string="Contribution Recipient NIPC",
        help="Tax number of the entity receiving the mandatory employee deduction.",
    )
    l10n_pt_ss_nature_code = fields.Selection(
        selection=[
            ("A", "A - Travel and Transport Allowances"),
            ("B", "B - Monthly Bonuses"),
            ("C", "C - Commissions"),
            ("D", "D - Termination Compensation"),
            ("F", "F - Holiday Subsidy"),
            ("H", "H - Concurrent Service Fees"),
            ("I", "I - Intermittent Contract Compensation"),
            ("M", "M - Regular Monthly Allowances"),
            ("N", "N - Christmas Subsidy"),
            ("O", "O - Non-monthly Bonuses"),
            ("P", "P - Base Pay"),
            ("R", "R - Meal Allowance"),
            ("S", "S - Overtime"),
            ("T", "T - Night Work"),
            ("X", "X - Regular Non-monthly Allowances"),
            ("2", "2 - Unused Holiday Pay on Termination"),
            ("6", "6 - Pay Differences (Legacy DR)"),
        ],
        string="SS Remuneration Nature",
    )
    l10n_pt_ss_contribution_base = fields.Selection(
        selection=[("include", "Include"), ("exclude", "Exclude")],
        string="SS Contribution Base",
        help="Leave empty to retain the BASIC salary category behavior. "
        "Rules affecting contributions must run before the SS deduction.",
    )

    @api.constrains("code", "l10n_pt_ss_contribution_base")
    def _check_l10n_pt_ss_contribution_rule_code(self):
        for rule in self:
            if rule.l10n_pt_ss_contribution_base and not (rule.code or "").strip():
                raise ValidationError(
                    self.env._(
                        "A rule affecting the SS contribution base needs a code."
                    )
                )
