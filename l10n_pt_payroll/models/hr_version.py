# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrVersion(models.Model):
    _inherit = "hr.version"

    l10n_pt_irs_family_status = fields.Selection(
        [
            ("single", "Single"),
            ("married_single_income", "Married - single income"),
            ("married_joint", "Married - both filers"),
        ],
        string="IRS Family Status",
        tracking=True,
    )
    l10n_pt_irs_dependents = fields.Integer(
        string="IRS Dependents",
        help="Number of dependents for IRS purposes; may differ from "
        "dependent children (e.g. ascendentes).",
        tracking=True,
    )
    l10n_pt_irs_disabled_dependents = fields.Integer(
        string="IRS Disabled Dependents",
        help="Dependents with a disability of 60% or more.",
        tracking=True,
    )
    l10n_pt_irs_disabled_dep_factor = fields.Integer(
        string="Disabled Dependent Deduction Factor",
        default=1,
        help="Despacho n.6: the per-disabled-dependent deduction may "
        "be multiplied, up to 3 times for single workers and married "
        "workers filing alone, up to 6 times for married workers "
        "filing jointly. The employee communicates the chosen factor "
        "to the payer.",
        tracking=True,
    )
    l10n_pt_irs_spouse_disabled = fields.Boolean(
        string="Disabled Spouse (no income)",
        help="Despacho n.5-b: for a married worker filing alone, the "
        "spouse has a permanent disability of 60% or more and no "
        "category A or H income.",
        tracking=True,
    )
    l10n_pt_military_disabled = fields.Boolean(
        string="Armed Forces Disability",
        help="Despacho n.5-d: the pensioner has an armed forces "
        "disability (Decretos-Leis 43/76 and 314/90); adds the flat "
        "pension deduction on tables X and XI.",
        tracking=True,
    )
    l10n_pt_irs_region = fields.Selection(
        [
            ("continente", "Continente"),
            ("acores", "Açores"),
            ("madeira", "Madeira"),
        ],
        string="IRS Region",
        compute="_compute_l10n_pt_irs_region",
        store=True,
        readonly=False,
        help="Tax region used to pick the withholding table set. "
        "Suggested from the employee's address (state district or "
        "postal code) while empty; kept once set, so update it "
        "manually if the employee moves to another region.",
        tracking=True,
    )
    l10n_pt_irs_pensioner = fields.Boolean(
        string="Pensioner",
        help="The worker receives a pension: the pension withholding "
        "tables (VIII-XI) apply instead of the dependent work tables "
        "(I-VII).",
        tracking=True,
    )
    l10n_pt_irs_non_resident = fields.Boolean(
        string="Non-Resident",
        help="The employee is not a tax resident in Portugal: a flat "
        "25% withholding applies without table deductions.",
        tracking=True,
    )
    l10n_pt_irs_preferred_rate = fields.Float(
        string="Preferred IRS Rate (%)",
        help="Optional flat withholding rate chosen by the employee "
        "(art. 98 n.6 CIRS): replaces the marginal rate but keeps the "
        "table deductions.",
        tracking=True,
    )
    l10n_pt_irs_jovem = fields.Boolean(
        string="IRS Jovem",
        help="The employee opted in to the young-worker partial "
        "exemption (art. 12-B CIRS).",
        tracking=True,
    )
    l10n_pt_irs_income_years = fields.Integer(
        string="Years of Income",
        help="Years of category A/B income already obtained; drives "
        "the IRS Jovem exemption percentage.",
        tracking=True,
    )
    l10n_pt_irs_table_id = fields.Many2one(
        "l10n.pt.irs.withholding.table",
        string="IRS Withholding Table",
        compute="_compute_l10n_pt_irs_table_id",
        store=True,
        tracking=True,
    )

    # The applicable IRS withholding table variant (I-VII, dependent work
    # income) is derived from the declared determinants: family situation,
    # number of dependents and disability degree >= 60%, per the annual
    # Despacho approving the tables.
    @api.depends(
        "l10n_pt_irs_family_status",
        "l10n_pt_irs_dependents",
        "l10n_pt_disability_degree",
        "l10n_pt_irs_pensioner",
    )
    def _compute_l10n_pt_irs_table_id(self):
        tables = {
            table.code: table
            for table in self.env["l10n.pt.irs.withholding.table"].search([])
        }
        empty_table = self.env["l10n.pt.irs.withholding.table"].browse()
        for version in self:
            code = version._l10n_pt_irs_table_code()
            version.l10n_pt_irs_table_id = tables.get(code, empty_table)

    def _l10n_pt_irs_table_code(self):
        self.ensure_one()
        status = self.l10n_pt_irs_family_status
        if not status:
            return False
        has_dependents = bool(self.l10n_pt_irs_dependents)
        disabled = (self.l10n_pt_disability_degree or 0) >= 60
        if self.l10n_pt_irs_pensioner:
            # Pension tables VIII-XI do not distinguish dependents,
            # only family situation and disability.
            if status == "married_single_income":
                return "XI" if disabled else "IX"
            return "X" if disabled else "VIII"
        if disabled:
            if status == "married_single_income":
                return "VII"
            if status == "single":
                return "V" if has_dependents else "IV"
            return "VI" if has_dependents else "IV"
        if status == "married_single_income":
            return "III"
        if status == "single" and has_dependents:
            return "II"
        return "I"

    @api.constrains("l10n_pt_irs_disabled_dep_factor", "l10n_pt_irs_family_status")
    def _check_l10n_pt_irs_disabled_dep_factor(self):
        # Despacho n.6: the multiplier is capped at 3 for single and
        # married-single-income workers, 6 for married joint filers.
        for version in self:
            factor = version.l10n_pt_irs_disabled_dep_factor or 0
            limit = 6 if version.l10n_pt_irs_family_status == "married_joint" else 3
            if not 1 <= factor <= limit:
                raise ValidationError(
                    self.env._(
                        "The disabled dependent deduction factor must be "
                        "between 1 and %(limit)s for the %(status)s family "
                        "status.",
                        limit=limit,
                        status=version.l10n_pt_irs_family_status or "unset",
                    )
                )

    # Suggest the tax region from the employee's private address: the PT
    # state districts map directly (20 = Açores, 30 = Madeira); when no
    # state is set, fall back to the postal code prefix (9xxx covers the
    # islands, 9500+ is Açores). A manually chosen region is kept.
    @api.depends("private_state_id", "private_zip")
    def _compute_l10n_pt_irs_region(self):
        for version in self:
            if version.l10n_pt_irs_region:
                continue
            version.l10n_pt_irs_region = version._l10n_pt_irs_region_from_address()

    def _l10n_pt_irs_region_from_address(self):
        self.ensure_one()
        state_code = self.private_state_id.code or ""
        if state_code == "20":
            return "acores"
        if state_code == "30":
            return "madeira"
        if state_code:
            return "continente"
        zip_code = (self.private_zip or "").strip()[:4]
        if zip_code.isdigit() and zip_code.startswith("9"):
            return "madeira" if int(zip_code) < 9500 else "acores"
        return "continente"
