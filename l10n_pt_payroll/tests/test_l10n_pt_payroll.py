# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import xml.etree.ElementTree as ET

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import format_amount

CSV_HEADER = (
    "date_start,date_end,region,table_code,lower_bound,upper_bound,"
    "marginal_rate,parcela_abater,dependent_parcela,"
    "forces_disabled_parcela,effective_rate_limit,ias,"
    "disabled_dep_parcela_single,disabled_dep_parcela_joint,"
    "spouse_disabled_parcela,"
    "pension_dep_parcela_single,pension_dep_parcela_joint,"
    "pension_dep_parcela_single_income\n"
)
# Set-level Despacho constants used by the test tables:
# IAS, disabled-dep single/joint, spouse-disabled, pension-dep
# single/joint/single-income.
SET_VALUES = "522.50,50,25,0,0,0,0"

_HISTORY_RULE_XMLIDS = {
    "GROSS": "l10n_pt_payroll.hr_rule_pt_gross",
    "IRS": "l10n_pt_payroll.hr_rule_pt_irs",
    "PT_IRS_BASE": "l10n_pt_payroll.hr_rule_pt_irs_base",
    "PT_IRS_ALLOWANCE": "l10n_pt_payroll.hr_rule_pt_irs_allowance",
    "PT_NATAL": "l10n_pt_payroll.hr_rule_pt_natal",
}


class TestL10nPtPayroll(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure = cls.env.ref("l10n_pt_payroll.structure_pt")
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Test Employee",
                "company_id": cls.env.company.id,
            }
        )
        # Initialize the contract (hr.version) created at employee creation
        cls.employee.version_id.write(
            {
                "contract_date_start": "2026-01-01",
                "contract_date_end": False,
                "wage": 1400.0,
                "struct_id": cls.structure.id,
                "resource_calendar_id": cls.env.company.resource_calendar_id.id,
                # IRS determinants: single, no dependents -> table I
                "l10n_pt_irs_family_status": "single",
                "l10n_pt_irs_region": "continente",
            }
        )
        cls.env["hr.pt.irs.withholding.import"]._import_csv_data(cls._test_csv())

    def setUp(self):
        super().setUp()
        # Tests share the class employee: reset the mutable IRS
        # determinants to the table-I baseline before each test.
        self.employee.write(
            {
                "l10n_pt_irs_dependents": 0,
                "l10n_pt_irs_disabled_dependents": 0,
                "l10n_pt_irs_disabled_dep_factor": 1,
                "l10n_pt_irs_spouse_disabled": False,
                "l10n_pt_military_disabled": False,
                "l10n_pt_irs_non_resident": False,
                "l10n_pt_irs_single_payer_declared": False,
                "l10n_pt_irs_preferred_rate": 0.0,
                "l10n_pt_irs_jovem": False,
                "l10n_pt_irs_income_years": 0,
            }
        )

    @staticmethod
    def _test_csv():
        """A minimal synthetic table set: two brackets on variants I,
        II and III, continente, covering 2026. Variant II is needed
        because dependents switch the derived table variant."""
        return CSV_HEADER + "".join(
            f"2026-01-01,2026-12-31,continente,{code},{lower},{upper},"
            f"{rate},{parcela},30,0,,{SET_VALUES}\n"
            for code in ("I", "II", "III")
            for lower, upper, rate, parcela in (
                ("0", "2000", "20", "0"),
                ("2000", "", "40", "200"),
            )
        )

    def _make_payslip(self):
        payslip = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2026-06-01",
                "date_to": "2026-06-30",
            }
        )
        payslip.onchange_employee()
        return payslip

    def test_pt_payroll_structure(self):
        self.assertEqual(self.structure.code, "PT")
        self.assertTrue(
            {
                "BASIC",
                "SA",
                "GROSS",
                "SS",
                "IRS",
                "SS_COMP",
                "SAT_COMP",
                "NET",
            }
            <= set(self.structure.rule_ids.mapped("code"))
        )

    def test_pt_payslip_compute(self):
        """A monthly payslip computes all PT lines, with the IRS
        retention resolved from the imported withholding table."""
        payslip = self._make_payslip()
        self.assertEqual(
            payslip.struct_id,
            self.structure,
            "The payslip uses the PT structure from the contract",
        )
        payslip.compute_sheet()

        lines = {line.code: line.total for line in payslip.line_ids}
        work100 = payslip.worked_days_line_ids.filtered(
            lambda line: line.code == "WORK100"
        )
        meal = 10.20 * work100.number_of_days
        # R = taxable BASIC only = 1400 -> first bracket: 20% of 1400
        self.assertAlmostEqual(lines["BASIC"], 1400.0)
        self.assertAlmostEqual(lines["SA"], meal)
        self.assertAlmostEqual(lines["GROSS"], 1400.0 + meal)
        self.assertAlmostEqual(lines["SS"], -0.11 * 1400.0)
        self.assertAlmostEqual(lines["IRS"], -280.0)
        self.assertAlmostEqual(lines["SS_COMP"], 0.2375 * 1400.0)
        self.assertAlmostEqual(lines["SAT_COMP"], 0.0)
        self.assertAlmostEqual(lines["NET"], 1400.0 + meal - 0.11 * 1400.0 - 280.0)

    def test_declaration_rule_defaults(self):
        """A payroll officer starts with known AT and SS mappings,
        not a guessed meal split."""
        rules = {rule.code: rule for rule in self.structure.rule_ids}
        basic = rules["BASIC"]
        self.assertEqual(basic.l10n_pt_dmr_at_role, "income")
        self.assertEqual(basic.l10n_pt_dmr_code, "A")
        self.assertEqual(basic.l10n_pt_ss_nature_code, "P")
        self.assertEqual(rules["IRS"].l10n_pt_dmr_at_role, "withholding")
        self.assertEqual(rules["SS"].l10n_pt_dmr_at_role, "contribution")
        for code in ("GROSS", "NET", "SS_COMP", "SAT_COMP"):
            self.assertEqual(rules[code].l10n_pt_dmr_at_role, "ignore")
        self.assertFalse(rules["SA"].l10n_pt_dmr_at_role)
        self.assertFalse(rules["SA"].l10n_pt_ss_nature_code)

    def test_social_security_base_configured_per_earning(self):
        """A payroll officer independently configures IRS and SS on additional pay."""
        allowances = self.env.ref("l10n_pt_payroll.categ_pt_alw")
        base = self.env.ref("l10n_pt_payroll.categ_pt_basic")
        extra_rules = self.env["hr.salary.rule"].create(
            [
                {
                    "name": "Contributory Addition",
                    "code": "SS_ADD",
                    "category_id": allowances.id,
                    "sequence": 30,
                    "amount_select": "fix",
                    "amount_fix": 200.0,
                    "l10n_pt_ss_contribution_base": "include",
                },
                {
                    "name": "IRS-only Addition",
                    "code": "IRS_ADD",
                    "category_id": base.id,
                    "sequence": 31,
                    "amount_select": "fix",
                    "amount_fix": 100.0,
                    "l10n_pt_irs_taxable": 1.0,
                    "l10n_pt_ss_contribution_base": "exclude",
                },
            ]
        )
        self.structure.rule_ids = [Command.link(rule.id) for rule in extra_rules]
        payslip = self._make_payslip()
        payslip.compute_sheet()

        lines = {line.code: line for line in payslip.line_ids}
        self.assertAlmostEqual(lines["IRS"].total, -300.0)
        self.assertAlmostEqual(lines["SS"].total, -176.0)
        self.assertAlmostEqual(lines["SS_COMP"].total, 380.0)
        # The SS lines expose the signed contribution base in amount
        # and the regime rate in rate so reports show base x rate.
        self.assertAlmostEqual(lines["SS"].amount, -1600.0)
        self.assertAlmostEqual(lines["SS"].rate, 11.0)
        self.assertAlmostEqual(lines["SS_COMP"].amount, 1600.0)
        self.assertAlmostEqual(lines["SS_COMP"].rate, 23.75)
        self.assertAlmostEqual(lines["PT_SS_BASE"].total, 1600.0)
        self.assertFalse(lines["PT_SS_BASE"].appears_on_payslip)
        self.assertIn("11.0000%", lines["SS"].name)
        self.assertIn("23.7500%", lines["SS_COMP"].name)
        # IRS keeps the booked retention as amount at rate 100 and
        # embeds the basis and applied rates in the line name.
        self.assertAlmostEqual(lines["IRS"].amount, -300.0)
        self.assertAlmostEqual(lines["IRS"].rate, 100.0)
        currency = self.env.company.currency_id
        self.assertIn(
            f"Taxable base: {format_amount(self.env, 1500.0, currency)}",
            lines["IRS"].name,
        )
        self.assertIn("applied rate: 20.000%", lines["IRS"].name)
        self.assertIn(
            f"formula deductions: {format_amount(self.env, 0.0, currency)}",
            lines["IRS"].name,
        )
        self.assertIn("monthly effective withholding rate: 20.00%", lines["IRS"].name)

    def test_social_security_fractional_base_precision_fallback(self):
        """A fractional contribution base that column rounding would push
        across a cent boundary falls back to the booked total in Amount
        at rate 100, with the base shown in the line name instead."""
        fractional = self.env["hr.salary.rule"].create(
            {
                "name": "Fractional Contributory Addition",
                "code": "SS_FRAC",
                "category_id": self.env.ref("l10n_pt_payroll.categ_pt_alw").id,
                "sequence": 32,
                "amount_select": "percentage",
                "amount_percentage": 10.029,
                "amount_percentage_base": "categories.BASIC",
                "l10n_pt_ss_contribution_base": "include",
            }
        )
        self.structure.rule_ids = [Command.link(fractional.id)]
        payslip = self._make_payslip()
        payslip.compute_sheet()

        lines = {line.code: line for line in payslip.line_ids}
        # Base = 1400 + 10.029% x 1400 = 1540.406; employee contribution
        # = -1540.406 x 11% = -169.44466 books as -169.44, while the
        # rounded Amount/Rate columns would recompute -169.45, so the
        # rule falls back to the total at rate 100.
        self.assertAlmostEqual(lines["SS"].total, -169.44)
        self.assertAlmostEqual(lines["SS"].amount, -169.44)
        self.assertAlmostEqual(lines["SS"].rate, 100.0)
        self.assertIn("11.0000%", lines["SS"].name)
        self.assertIn("Contribution base:", lines["SS"].name)
        # The employer rate does not cross a rounding boundary on the
        # same base: it keeps the native base/rate columns.
        self.assertAlmostEqual(lines["SS_COMP"].amount, 1540.41)
        self.assertAlmostEqual(lines["SS_COMP"].rate, 23.75)
        self.assertIn("23.7500%", lines["SS_COMP"].name)
        self.assertNotIn("Contribution base:", lines["SS_COMP"].name)
        self.assertAlmostEqual(lines["PT_SS_BASE"].total, 1540.41)

    def test_social_security_rates_from_regime(self):
        """The SS rates come from the employee's Social Security regime:
        changing the regime rates changes the payslip lines, and the SAT
        premium comes from the employee's work insurance policy."""
        regime = self.employee.l10n_pt_ss_regime_id
        regime.write(
            {
                "l10n_pt_employee_rate": 10.0,
                "l10n_pt_employer_rate": 20.0,
            }
        )
        insurer = self.env["res.partner"].create({"name": "Test Insurer"})
        policy = self.env["l10n.pt.work.insurance"].create(
            {
                "insurer_id": insurer.id,
                "policy_number": "SAT-001",
                "rate": 1.5,
            }
        )
        self.employee.l10n_pt_work_insurance_id = policy
        payslip = self._make_payslip()
        payslip.compute_sheet()

        lines = {line.code: line.total for line in payslip.line_ids}
        self.assertAlmostEqual(lines["SS"], -0.10 * 1400.0)
        self.assertAlmostEqual(lines["SS_COMP"], 0.20 * 1400.0)
        self.assertAlmostEqual(lines["SAT_COMP"], 0.015 * 1400.0)

    def test_ss_regime_seed_data(self):
        """The bundled regime records carry the official situacao
        contributiva rates and DR rate codes."""
        cases = {
            "l10n_pt_ss_regime_geral": (11.0, 23.75, "000"),
            "l10n_pt_ss_regime_pre_reforma": (11.0, 23.75, "123"),
            "l10n_pt_ss_regime_moe_gerencia": (11.0, 23.75, "142"),
            "l10n_pt_ss_regime_moe_geral": (9.3, 20.3, "669"),
            "l10n_pt_ss_regime_moe_ipss": (9.9, 22.3, "183"),
        }
        for xmlid, (employee, employer, dr_code) in cases.items():
            regime = self.env.ref(f"l10n_pt_hr.{xmlid}")
            with self.subTest(regime=regime.code):
                self.assertEqual(regime.l10n_pt_employee_rate, employee)
                self.assertEqual(regime.l10n_pt_employer_rate, employer)
                self.assertEqual(regime.l10n_pt_dr_code, dr_code)
                self.assertAlmostEqual(regime.l10n_pt_total_rate, employee + employer)

    def test_irs_retention_preferred_rate(self):
        """A preferred rate replaces only the marginal rate (Despacho
        n.5-e): the table deductions still apply."""
        self.employee.write(
            {
                "l10n_pt_irs_preferred_rate": 25.0,
                "l10n_pt_irs_dependents": 2,
            }
        )
        payslip = self._make_payslip()
        payslip.compute_sheet()
        lines = {line.code: line.total for line in payslip.line_ids}
        # 1400 * 25% - 30 * 2 = 350 - 60 = 290
        self.assertAlmostEqual(lines["IRS"], -290.0)

    def test_irs_retention_non_resident(self):
        """A non-resident is withheld a flat 25% without any table
        deduction."""
        self.employee.l10n_pt_irs_non_resident = True
        payslip = self._make_payslip()
        payslip.compute_sheet()
        lines = {line.code: line.total for line in payslip.line_ids}
        self.assertAlmostEqual(lines["IRS"], -0.25 * 1400.0)
        irs_line = payslip.line_ids.filtered(lambda line: line.code == "IRS")
        # The flat 25% rate and the unadjusted base appear in the name,
        # unlike the progressive table path.
        self.assertIn("applied rate: 25.000%", irs_line.name)
        self.assertIn(
            f"Taxable base: "
            f"{format_amount(self.env, 1400.0, self.env.company.currency_id)}",
            irs_line.name,
        )
        self.assertIn("monthly effective withholding rate: 25.00%", irs_line.name)
        self.assertNotIn("income before relief", irs_line.name)

    def test_irs_retention_dependents(self):
        """Dependents reduce the retention through the per-dependent
        parcela; three or more also drop the marginal rate by 1 p.p."""
        self.employee.write(
            {
                "l10n_pt_irs_dependents": 2,
                "l10n_pt_irs_disabled_dependents": 1,
            }
        )
        payslip = self._make_payslip()
        payslip.compute_sheet()
        lines = {line.code: line.total for line in payslip.line_ids}
        # 1400 * 20% - 30 * 2 - 50 * 1 = 280 - 110 = 170
        self.assertAlmostEqual(lines["IRS"], -170.0)
        # Three or more dependents: marginal rate 20% -> 19%
        self.employee.l10n_pt_irs_dependents = 3
        payslip = self._make_payslip()
        payslip.compute_sheet()
        lines = {line.code: line.total for line in payslip.line_ids}
        # 1400 * 19% - 30 * 3 - 50 * 1 = 266 - 140 = 126
        self.assertAlmostEqual(lines["IRS"], -126.0)

    def test_irs_retention_disabled_dep_factor(self):
        """Despacho n.6: the employee may multiply the per-disabled-
        dependent deduction — up to 3x for a single worker."""
        self.employee.write(
            {
                "l10n_pt_irs_family_status": "single",
                "l10n_pt_irs_disabled_dependents": 1,
                "l10n_pt_irs_disabled_dep_factor": 3,
            }
        )
        payslip = self._make_payslip()
        payslip.compute_sheet()
        lines = {line.code: line.total for line in payslip.line_ids}
        # 1400 * 20% - 50 * 1 * 3 = 280 - 150 = 130
        self.assertAlmostEqual(lines["IRS"], -130.0)

    def test_irs_retention_disabled_spouse(self):
        """Despacho n.5-b: a married worker filing alone gets an extra
        deduction when the spouse is disabled and has no A/H income."""
        self.employee.write(
            {
                "l10n_pt_irs_family_status": "married_single_income",
                "l10n_pt_irs_spouse_disabled": True,
            }
        )
        variant_iii = self.env.ref("l10n_pt_hr.l10n_pt_irs_table_3")
        table = self.env["hr.pt.irs.withholding.table"].search(
            [
                ("region", "=", "continente"),
                ("table_id", "=", variant_iii.id),
            ],
            limit=1,
        )
        table.spouse_disabled_parcela = 100.0
        payslip = self._make_payslip()
        payslip.compute_sheet()
        lines = {line.code: line.total for line in payslip.line_ids}
        # table III bracket: 1400 * 20% - 100 = 180
        self.assertAlmostEqual(lines["IRS"], -180.0)

    def test_irs_retention_jovem(self):
        """IRS Jovem withholds on the non-exempt portion: income year 5
        exempts 50% of the income up to 55 x IAS, taxed at the effective
        rate of the full income per AT Circular 20274/2025."""
        # June-only overlay: the exemption base is taxed through the
        # effective rate, not a second marginal bracket.
        self.env["hr.pt.irs.withholding.import"]._import_csv_data(
            CSV_HEADER
            + "2026-06-01,2026-06-30,continente,I,0,920,0,0,0,0,,"
            + SET_VALUES
            + "\n"
            + "2026-06-01,2026-06-30,continente,I,920,,24.1,193.33,0,0,,"
            + SET_VALUES
            + "\n"
        )
        self.employee.write(
            {
                "l10n_pt_irs_jovem": True,
                "l10n_pt_irs_income_years": 4,  # 5th year -> 50%
            }
        )
        payslip = self._make_payslip()
        payslip.compute_sheet()
        lines = {line.code: line.total for line in payslip.line_ids}
        # exempt = min(1400 * 0.5, 55 * 522.50 / 14) = 700 -> base = 700
        # full-income retention 144.07 -> effective 10.291% on 700 -> 72
        self.assertAlmostEqual(lines["IRS"], -72.0)
        irs_line = payslip.line_ids.filtered(lambda line: line.code == "IRS")
        currency = self.env.company.currency_id
        self.assertIn(
            f"Taxable base: {format_amount(self.env, 700.0, currency)}",
            irs_line.name,
        )
        self.assertIn(
            f"income before relief: {format_amount(self.env, 1400.0, currency)}",
            irs_line.name,
        )
        self.assertIn("applied rate: 10.291%", irs_line.name)
        self.assertIn("monthly effective withholding rate: 5.14%", irs_line.name)
        # Above the annual cap the exemption stops at 55 x IAS / 14:
        # wage 5000 -> exempt 2052.68 -> base 2947.32, retention 596.
        self.employee.version_id.wage = 5000.0
        payslip = self._make_payslip()
        payslip.compute_sheet()
        self.employee.version_id.wage = 1400.0
        lines = {line.code: line.total for line in payslip.line_ids}
        self.assertAlmostEqual(lines["IRS"], -596.0)
        # First income year exempts the whole base: no rate is applied
        # and the name builder must not divide by the zero base.
        self.employee.l10n_pt_irs_income_years = 0
        payslip = self._make_payslip()
        payslip.compute_sheet()
        irs_line = payslip.line_ids.filtered(lambda line: line.code == "IRS")
        self.assertEqual(irs_line.total, 0.0)
        self.assertNotIn("applied rate", irs_line.name)
        self.assertIn("monthly effective withholding rate: 0.00%", irs_line.name)

    def test_irs_selects_table_at_period_end(self):
        """The payslip period end selects the withholding table: a
        period ending July 1 falls under the July table set."""
        # June work period paid July 1 uses the July table set.
        self.env["hr.pt.irs.withholding.import"]._import_csv_data(
            CSV_HEADER
            + "2026-07-01,2026-07-31,continente,I,0,,10,0,0,0,,"
            + SET_VALUES
            + "\n"
        )
        payslip = self._make_payslip()
        payslip.date_to = "2026-07-01"
        payslip.onchange_employee()
        payslip.compute_sheet()
        self.assertEqual(payslip.date_from.isoformat(), "2026-06-01")
        self.assertEqual(payslip.date_to.isoformat(), "2026-07-01")
        lines = {line.code: line.total for line in payslip.line_ids}
        # July overlay: single open bracket at 10% -> 1400 * 10% = 140
        self.assertAlmostEqual(lines["IRS"], -140.0)

    def test_irs_non_resident_single_payer_allowance(self):
        """CIRS art. 71: a non-resident with the written single-payer
        declaration on file may use part of the monthly minimum-wage
        allowance through the Other Inputs row; without the declaration
        the payslip refuses it."""
        self.employee.l10n_pt_irs_non_resident = True
        payslip = self._make_payslip()
        allowance = payslip.input_line_ids.filtered(
            lambda line: line.code == "PT_IRS_SINGLE_PAYER"
        )
        self.assertEqual(len(allowance), 1)
        allowance.amount = 920.0
        with self.assertRaises(UserError):
            payslip.compute_sheet()
        self.employee.l10n_pt_irs_single_payer_declared = True
        payslip.compute_sheet()
        lines = {line.code: line for line in payslip.line_ids}
        # base = 1400 - 920 = 480 -> 480 * 25% = 120
        self.assertAlmostEqual(lines["IRS"].total, -120.0)
        irs_line = lines["IRS"]
        currency = self.env.company.currency_id
        self.assertIn(
            f"Taxable base: {format_amount(self.env, 480.0, currency)}",
            irs_line.name,
        )
        self.assertIn(
            f"income before relief: {format_amount(self.env, 1400.0, currency)}",
            irs_line.name,
        )
        self.assertIn(
            f"single-payer allowance applied: "
            f"{format_amount(self.env, 920.0, currency)}",
            irs_line.name,
        )
        self.assertIn("monthly effective withholding rate: 8.57%", irs_line.name)
        # Hidden helper lines record this payment's taxable base and
        # the allowance actually applied.
        base_line = lines["PT_IRS_BASE"]
        self.assertAlmostEqual(base_line.total, 1400.0)
        self.assertAlmostEqual(base_line.amount, 1400.0)
        self.assertAlmostEqual(base_line.rate, 100.0)
        allowance_line = lines["PT_IRS_ALLOWANCE"]
        self.assertAlmostEqual(allowance_line.total, 920.0)
        for helper in (base_line, allowance_line):
            self.assertFalse(helper.appears_on_payslip)
        relieved = {code: lines[code].total for code in ("GROSS", "SS", "SS_COMP")}
        # A zero input leaves the full base taxable and does not touch
        # the earnings or Social Security lines.
        allowance.amount = 0.0
        payslip.compute_sheet()
        lines = {line.code: line for line in payslip.line_ids}
        self.assertAlmostEqual(lines["IRS"].total, -350.0)
        for code in ("GROSS", "SS", "SS_COMP"):
            self.assertAlmostEqual(lines[code].total, relieved[code])
        # Allowance larger than the payment leaves nothing to withhold.
        allowance.amount = 500.0
        self.employee.version_id.wage = 400.0
        payslip.compute_sheet()
        self.employee.version_id.wage = 1400.0
        lines = {line.code: line for line in payslip.line_ids}
        self.assertAlmostEqual(lines["IRS"].total, 0.0)
        irs_line = lines["IRS"]
        self.assertIn(
            f"single-payer allowance applied: "
            f"{format_amount(self.env, 400.0, currency)}",
            irs_line.name,
        )
        self.assertIn("monthly effective withholding rate: 0.00%", irs_line.name)
        # The recorded allowance is capped at the payment, not the
        # 500 entered on the input row.
        self.assertAlmostEqual(lines["PT_IRS_ALLOWANCE"].total, 400.0)

    def test_irs_single_payer_rejects_invalid_inputs(self):
        """The Other Inputs row rejects negative amounts and a second
        row for the same contract."""
        payslip = self._make_payslip()
        allowance = payslip.input_line_ids.filtered(
            lambda line: line.code == "PT_IRS_SINGLE_PAYER"
        )
        self.assertEqual(len(allowance), 1)
        allowance.amount = -50.0
        with self.assertRaisesRegex(UserError, "non-negative"):
            payslip.compute_sheet()
        allowance.amount = 0.0
        self.env["hr.payslip.input"].create(
            {
                "name": "Dedução de Entidade Única Neste Pagamento",
                "code": "PT_IRS_SINGLE_PAYER",
                "amount": 0.0,
                "contract_id": payslip.contract_id.id,
                "payslip_id": payslip.id,
            }
        )
        with self.assertRaisesRegex(UserError, "only one single-payer"):
            payslip.compute_sheet()

    def test_irs_accumulates_finalized_payments(self):
        """Done payslips accumulate the monthly withholding: each later
        slip books only the incremental amount on the month total."""
        self.employee.version_id.wage = 800.0
        first = self._make_payslip()
        first.payment_date = "2026-06-10"
        first.action_payslip_done()
        self.assertAlmostEqual(
            first.line_ids.filtered(lambda line: line.code == "IRS").total, -160.0
        )
        # The helper lines record each payment's own taxable base, not
        # the cumulative month total used inside the IRS calculation.
        first_lines = {line.code: line for line in first.line_ids}
        self.assertAlmostEqual(first_lines["PT_IRS_BASE"].amount, 800.0)
        self.assertAlmostEqual(first_lines["PT_IRS_ALLOWANCE"].total, 0.0)
        # The contract wage changed, but the finalized slip keeps its
        # recorded taxable base.
        self.employee.version_id.wage = 1400.0
        second = self._make_payslip()
        second.payment_date = "2026-06-20"
        second.compute_sheet()
        # Month total: (800 + 1400) taxable -> 2200 * 40% - 200 = 680,
        # less the 160 already withheld on the first slip.
        self.assertAlmostEqual(
            second.line_ids.filtered(lambda line: line.code == "IRS").total, -520.0
        )
        second_lines = {line.code: line for line in second.line_ids}
        self.assertAlmostEqual(second_lines["PT_IRS_BASE"].amount, 1400.0)
        self.assertEqual(second.state, "verify")
        third = self._make_payslip()
        third.payment_date = "2026-06-30"
        for _ in range(2):
            third.compute_sheet()
            self.assertAlmostEqual(
                third.line_ids.filtered(lambda line: line.code == "IRS").total, -520.0
            )
        third_irs = third.line_ids.filtered(lambda line: line.code == "IRS")
        currency = self.env.company.currency_id
        self.assertIn(
            f"month-to-date withholding: {format_amount(self.env, 680.0, currency)}",
            third_irs.name,
        )
        self.assertIn(
            f"previously withheld: {format_amount(self.env, 160.0, currency)}",
            third_irs.name,
        )
        # The finalized slip is untouched by later computations.
        self.assertAlmostEqual(
            first.line_ids.filtered(lambda line: line.code == "IRS").total, -160.0
        )

    def test_irs_accumulates_income_below_threshold(self):
        """Accumulation applies the monthly bracket to the combined
        income, so a second slip can cross into a taxed bracket."""
        self.env["hr.pt.irs.withholding.import"]._import_csv_data(
            CSV_HEADER
            + "2026-06-01,2026-06-30,continente,I,0,920,0,0,0,0,,"
            + SET_VALUES
            + "\n"
            + "2026-06-01,2026-06-30,continente,I,920,,24.1,193.33,0,0,,"
            + SET_VALUES
            + "\n"
        )
        self.employee.version_id.wage = 800.0
        first = self._make_payslip()
        first.payment_date = "2026-06-10"
        first.action_payslip_done()
        self.assertAlmostEqual(
            first.line_ids.filtered(lambda line: line.code == "IRS").total, 0.0
        )
        self.employee.version_id.wage = 700.0
        second = self._make_payslip()
        second.payment_date = "2026-06-20"
        second.compute_sheet()
        # Combined 1500 crosses the 920 threshold: 1500 * 24.1% - 193.33
        # = 168.17 -> 168 withheld now (nothing withheld before).
        self.assertAlmostEqual(
            second.line_ids.filtered(lambda line: line.code == "IRS").total, -168.0
        )
        # A payslip in another month does not see June's payments.
        july = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            }
        )
        july.onchange_employee()
        july.compute_sheet()
        july_irs = july.line_ids.filtered(lambda line: line.code == "IRS")
        self.assertAlmostEqual(july_irs.total, -140.0)
        self.assertNotIn("month-to-date", july_irs.name)
        self.employee.version_id.wage = 1400.0

    def test_irs_batch_confirmation_rejects_multiple_payments(self):
        """Confirming several payslips for the same employee and month
        in one batch is refused; each payment is confirmed on its own."""
        first = self._make_payslip()
        first.payment_date = "2026-06-20"
        second = self._make_payslip()
        second.payment_date = "2026-06-20"
        slips = self.env["hr.payslip"].browse([first.id, second.id])
        slips.compute_sheet()
        for slip in slips:
            self.assertAlmostEqual(
                slip.line_ids.filtered(lambda line: line.code == "IRS").total, -280.0
            )
        # A batch state write covering both slips is refused by the
        # payment-order constraint (action_payslip_done is singleton).
        with self.assertRaisesRegex(ValidationError, "separately"), self.cr.savepoint():
            slips.write({"state": "done"})
        self.assertNotEqual(first.state, "done")
        self.assertNotEqual(second.state, "done")
        # Confirmed one at a time, the same payments accumulate normally.
        first.action_payslip_done()
        second.action_payslip_done()
        self.assertEqual(first.state, "done")
        self.assertEqual(second.state, "done")
        # Second slip: combined taxable 2800 -> 2800 * 40% - 200 = 920,
        # less the 280 withheld on the first.
        self.assertAlmostEqual(
            first.line_ids.filtered(lambda line: line.code == "IRS").total, -280.0
        )
        self.assertAlmostEqual(
            second.line_ids.filtered(lambda line: line.code == "IRS").total, -640.0
        )

    def test_irs_blocks_backdated_payslip(self):
        """A payslip ending before an already-finalized slip in the same
        month is refused for manual review."""
        first = self._make_payslip()
        first.payment_date = "2026-06-30"
        first.action_payslip_done()
        earlier = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2026-06-01",
                "date_to": "2026-06-15",
            }
        )
        earlier.payment_date = "2026-06-15"
        earlier.onchange_employee()
        with self.assertRaisesRegex(UserError, "backdated"):
            earlier.compute_sheet()

    def test_irs_uses_explicit_payment_month(self):
        """Payment Date selects the withholding month: a June payslip
        paid in July accumulates with other July payments."""
        self.env["hr.pt.irs.withholding.import"]._import_csv_data(
            CSV_HEADER
            + "2026-07-01,2026-07-31,continente,I,0,,10,0,0,0,,"
            + SET_VALUES
            + "\n"
        )
        first = self._make_payslip()
        first.payment_date = "2026-07-01"
        first.action_payslip_done()
        self.assertAlmostEqual(
            first.line_ids.filtered(lambda line: line.code == "IRS").total, -140.0
        )
        second = self._make_payslip()
        second.payment_date = "2026-07-02"
        second.compute_sheet()
        # July month total (1400 + 1400) * 10% = 280, less 140 withheld.
        second_irs = second.line_ids.filtered(lambda line: line.code == "IRS")
        self.assertAlmostEqual(second_irs.total, -140.0)
        currency = self.env.company.currency_id
        self.assertIn(
            f"month-to-date withholding: {format_amount(self.env, 280.0, currency)}",
            second_irs.name,
        )
        self.assertIn(
            f"previously withheld: {format_amount(self.env, 140.0, currency)}",
            second_irs.name,
        )
        # Blank Payment Date falls back to the period end (June), which
        # sees none of the July payments.
        third = self._make_payslip()
        third.compute_sheet()
        third_irs = third.line_ids.filtered(lambda line: line.code == "IRS")
        self.assertAlmostEqual(third_irs.total, -280.0)
        self.assertNotIn("month-to-date", third_irs.name)

    def test_irs_blocks_payment_date_before_confirmed_payment(self):
        """A slip paid before an already-confirmed payment for the same
        employee, company, and month is refused for manual review."""
        late = self._make_payslip()
        late.payment_date = "2026-07-15"
        late.action_payslip_done()
        early = self._make_payslip()
        early.payment_date = "2026-07-01"
        with self.assertRaisesRegex(UserError, "backdated"):
            with self.cr.savepoint():
                early.action_payslip_done()
        self.assertNotEqual(early.state, "done")

    def test_irs_requires_explicit_dates_for_multiple_payments(self):
        """A lone monthly payslip may leave Payment Date blank; once a
        month has several payments every payslip needs an explicit
        date, whichever side is confirmed first."""
        lone = self._make_payslip()
        lone.action_payslip_done()
        self.assertEqual(lone.state, "done")
        self.assertAlmostEqual(
            lone.line_ids.filtered(lambda line: line.code == "IRS").total, -280.0
        )
        # A second June payment conflicts because the confirmed slip
        # has no Payment Date — even an explicitly dated slip is refused.
        june = self._make_payslip()
        june.payment_date = "2026-06-15"
        with self.assertRaisesRegex(UserError, "Set a payment date"):
            with self.cr.savepoint():
                june.action_payslip_done()
        self.assertNotEqual(june.state, "done")
        # Reverse order in July: the explicit payment confirms first,
        # then the blank payslip for the same month is refused.
        july_paid = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            }
        )
        july_paid.payment_date = "2026-07-10"
        july_paid.onchange_employee()
        july_paid.action_payslip_done()
        self.assertEqual(july_paid.state, "done")
        july_blank = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            }
        )
        july_blank.onchange_employee()
        with self.assertRaisesRegex(UserError, "Set a payment date"):
            with self.cr.savepoint():
                july_blank.action_payslip_done()
        self.assertNotEqual(july_blank.state, "done")

    def test_christmas_subsidy_on_regular_payslip(self):
        """A Christmas subsidy entered through Other Inputs is paid
        alongside the salary: it joins the SS base and is withheld
        separately from the monthly IRS."""
        payslip = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2026-11-01",
                "date_to": "2026-11-30",
            }
        )
        payslip.payment_date = "2026-11-30"
        payslip.onchange_employee()
        subsidy = payslip.input_line_ids.filtered(lambda line: line.code == "PT_NATAL")
        self.assertEqual(len(subsidy), 1)
        subsidy.amount = 1400.0
        payslip.compute_sheet()
        lines = {line.code: line for line in payslip.line_ids}
        self.assertAlmostEqual(lines["BASIC"].total, 1400.0)
        self.assertAlmostEqual(lines["PT_NATAL"].total, 1400.0)
        self.assertAlmostEqual(lines["IRS"].total, -280.0)
        self.assertAlmostEqual(lines["PT_NATAL_IRS"].total, -280.0)
        # SS base = 1400 salary + 1400 subsidy -> 2800.
        self.assertAlmostEqual(lines["SS"].total, -308.0)
        self.assertAlmostEqual(lines["SS_COMP"].total, 665.0)
        self.assertAlmostEqual(lines["PT_IRS_BASE"].total, 1400.0)
        meal = lines["SA"].total
        self.assertAlmostEqual(lines["GROSS"].total, 2800.0 + meal)
        self.assertAlmostEqual(lines["NET"].total, lines["GROSS"].total - 868.0)
        natal_rule = self.env.ref("l10n_pt_payroll.hr_rule_pt_natal")
        self.assertEqual(natal_rule.l10n_pt_dmr_code, "A4")
        self.assertEqual(natal_rule.l10n_pt_ss_nature_code, "N")

    def _make_natal_payslip(self, date_to, payment_date, amount):
        payslip = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": f"{date_to[:7]}-01",
                "date_to": date_to,
                "struct_id": self.env.ref("l10n_pt_payroll.structure_pt_natal").id,
            }
        )
        payslip.payment_date = payment_date
        payslip.onchange_employee()
        subsidy = payslip.input_line_ids.filtered(lambda line: line.code == "PT_NATAL")
        self.assertEqual(len(subsidy), 1)
        subsidy.amount = amount
        return payslip

    def _make_monthly_natal_payslip(self, date_to, payment_date, amount=1400.0):
        """A regular payslip opting in to the monthly Christmas subsidy
        installments with the reviewed annual entitlement."""
        payslip = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": f"{date_to[:7]}-01",
                "date_to": date_to,
            }
        )
        payslip.payment_date = payment_date
        payslip.onchange_employee()
        subsidy = payslip.input_line_ids.filtered(
            lambda line: line.code == "PT_NATAL_MONTHLY"
        )
        self.assertEqual(len(subsidy), 1)
        subsidy.amount = amount
        return payslip

    def _make_ferias_payslip(
        self, date_to, payment_date, amount, target=None, standalone=False
    ):
        """A payslip carrying the reviewed annual holiday subsidy
        entitlement and optional cumulative amount due."""
        vals = {
            "employee_id": self.employee.id,
            "date_from": f"{date_to[:7]}-01",
            "date_to": date_to,
        }
        if standalone:
            vals["struct_id"] = self.env.ref("l10n_pt_payroll.structure_pt_ferias").id
        payslip = self.env["hr.payslip"].create(vals)
        if payment_date:
            payslip.payment_date = payment_date
        payslip.onchange_employee()
        subsidy = payslip.input_line_ids.filtered(lambda line: line.code == "PT_FERIAS")
        self.assertEqual(len(subsidy), 1)
        subsidy.amount = amount
        if target is not None:
            target_input = payslip.input_line_ids.filtered(
                lambda line: line.code == "PT_FERIAS_TARGET"
            )
            self.assertEqual(len(target_input), 1)
            target_input.amount = target
        return payslip

    def _make_ferias_monthly_payslip(
        self, date_to, payment_date, amount=1400.0, standalone=False
    ):
        """A payslip opting in to monthly holiday subsidy installments
        with the reviewed annual entitlement."""
        payslip = self._make_ferias_payslip(
            date_to, payment_date, 0.0, standalone=standalone
        )
        monthly = payslip.input_line_ids.filtered(
            lambda line: line.code == "PT_FERIAS_MONTHLY"
        )
        self.assertEqual(len(monthly), 1)
        monthly.amount = amount
        return payslip

    def test_christmas_subsidy_on_standalone_payslip(self):
        """The standalone Christmas structure pays only the verified,
        operator-prorated subsidy with its own withholding."""
        payslip = self._make_natal_payslip("2026-12-15", "2026-12-15", 700.0)
        payslip.compute_sheet()
        lines = {line.code: line for line in payslip.line_ids}
        for absent in ("BASIC", "SA", "IRS", "PT_IRS_BASE"):
            self.assertNotIn(absent, lines)
        self.assertAlmostEqual(lines["PT_NATAL"].total, 700.0)
        self.assertAlmostEqual(lines["PT_NATAL_IRS"].total, -140.0)
        self.assertAlmostEqual(lines["SS"].total, -77.0)
        self.assertAlmostEqual(lines["SS_COMP"].total, 166.25)
        self.assertAlmostEqual(lines["GROSS"].total, 700.0)
        self.assertAlmostEqual(lines["NET"].total, 483.0)
        payslip.action_payslip_done()
        self.assertEqual(payslip.state, "done")
        # A regular December payslip is unaffected: ordinary IRS only.
        regular = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2026-12-01",
                "date_to": "2026-12-31",
            }
        )
        regular.payment_date = "2026-12-31"
        regular.onchange_employee()
        regular.compute_sheet()
        regular_lines = {line.code: line for line in regular.line_ids}
        self.assertAlmostEqual(regular_lines["IRS"].total, -280.0)
        self.assertNotIn("PT_NATAL", regular_lines)
        gross_before = regular_lines["GROSS"].total
        net_before = regular_lines["NET"].total
        # The input is the reviewed annual entitlement: with the full
        # 700 already paid, the payslip records the entitlement and a
        # signed correction that cancels it — nothing more is payable
        # and no subsidy IRS is withheld.
        regular_subsidy = regular.input_line_ids.filtered(
            lambda line: line.code == "PT_NATAL"
        )
        self.assertEqual(len(regular_subsidy), 1)
        regular_subsidy.amount = 700.0
        regular.compute_sheet()
        regular_lines = {line.code: line for line in regular.line_ids}
        self.assertAlmostEqual(regular_lines["PT_NATAL"].total, 700.0)
        self.assertAlmostEqual(regular_lines["PT_NATAL_CORRECTION"].total, -700.0)
        self.assertNotIn("PT_NATAL_IRS", regular_lines)
        self.assertAlmostEqual(regular_lines["IRS"].total, -280.0)
        self.assertAlmostEqual(regular_lines["GROSS"].total, gross_before)
        self.assertAlmostEqual(regular_lines["NET"].total, net_before)
        # A revised entitlement is recorded in full, corrected by what
        # was already paid, and taxed on the whole subsidy less prior
        # withholding — the payable balance is what reaches gross.
        topup = self._make_natal_payslip("2026-12-20", "2026-12-20", 2600.0)
        topup.compute_sheet()
        topup_lines = {line.code: line for line in topup.line_ids}
        self.assertAlmostEqual(topup_lines["PT_NATAL"].total, 2600.0)
        self.assertAlmostEqual(topup_lines["PT_NATAL_CORRECTION"].total, -700.0)
        # Cumulative tax on 2600 is 840; 140 was already withheld.
        self.assertAlmostEqual(topup_lines["PT_NATAL_IRS"].total, -700.0)
        # Social Security applies to the payable balance only.
        self.assertAlmostEqual(topup_lines["SS"].total, -209.0)
        self.assertAlmostEqual(topup_lines["SS_COMP"].total, 451.25)
        self.assertAlmostEqual(topup_lines["PT_SS_BASE"].total, 1900.0)
        self.assertAlmostEqual(topup_lines["GROSS"].total, 1900.0)
        self.assertAlmostEqual(topup_lines["NET"].total, 991.0)
        topup.action_payslip_done()
        self.assertEqual(topup.state, "done")
        # Finalizing the top-up does not rewrite the recorded payment.
        first_lines = {line.code: line for line in payslip.line_ids}
        self.assertAlmostEqual(first_lines["PT_NATAL"].total, 700.0)
        self.assertAlmostEqual(first_lines["PT_NATAL_IRS"].total, -140.0)
        # The signed history nets to the revised entitlement
        # (700 + 2600 - 700), so a further payslip for the same amount
        # corrects the whole recorded value and pays nothing.
        settled = self._make_natal_payslip("2026-12-24", "2026-12-24", 2600.0)
        settled.compute_sheet()
        settled_lines = {line.code: line for line in settled.line_ids}
        self.assertAlmostEqual(settled_lines["PT_NATAL"].total, 2600.0)
        self.assertAlmostEqual(settled_lines["PT_NATAL_CORRECTION"].total, -2600.0)
        self.assertNotIn("PT_NATAL_IRS", settled_lines)
        self.assertAlmostEqual(settled_lines["GROSS"].total, 0.0)
        self.assertAlmostEqual(settled_lines["NET"].total, 0.0)

    def test_christmas_subsidy_rejects_missing_payment_date(self):
        """A subsidy input requires a Payment Date inside the payslip
        period year — the year that bounds the one-per-year payment."""
        payslip = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2026-11-01",
                "date_to": "2026-11-30",
            }
        )
        payslip.onchange_employee()
        subsidy = payslip.input_line_ids.filtered(lambda line: line.code == "PT_NATAL")
        self.assertEqual(len(subsidy), 1)
        subsidy.amount = 1400.0
        with self.assertRaisesRegex(UserError, "payment date"):
            payslip.compute_sheet()

    def test_christmas_subsidy_recomputes_on_confirm(self):
        """A second subsidy payslip confirmed after the first recomputes
        against the finalized payment: the signed lines net to zero."""
        first = self._make_natal_payslip("2026-12-15", "2026-12-15", 700.0)
        first.compute_sheet()
        second = self._make_natal_payslip("2026-12-20", "2026-12-20", 700.0)
        second.compute_sheet()
        first.action_payslip_done()
        self.assertEqual(first.state, "done")
        second.action_payslip_done()
        self.assertEqual(second.state, "done")
        lines = {line.code: line for line in second.line_ids}
        self.assertAlmostEqual(lines["PT_NATAL"].total, 700.0)
        self.assertAlmostEqual(lines["PT_NATAL_CORRECTION"].total, -700.0)
        self.assertNotIn("PT_NATAL_IRS", lines)
        self.assertAlmostEqual(lines["GROSS"].total, 0.0)
        self.assertAlmostEqual(lines["NET"].total, 0.0)

    def test_christmas_subsidy_balance_guards(self):
        """Prior payments above a revised entitlement, and finalized
        reversals, stop the balance calculation for manual review."""
        first = self._make_natal_payslip("2026-12-15", "2026-12-15", 700.0)
        first.compute_sheet()
        first.action_payslip_done()
        # A revised entitlement below what was already paid is a
        # correction case, not a negative earning.
        overpaid = self._make_natal_payslip("2026-12-20", "2026-12-20", 500.0)
        with self.assertRaisesRegex(UserError, "exceed the annual entitlement"):
            overpaid.compute_sheet()
        # A finalized reversal in the entitlement year requires manual
        # review instead of a silently recomputed balance.
        self._make_history_slip(
            "2026-12-31",
            payment_date="2026-12-22",
            credit_note=True,
            lines=(("PT_NATAL", 700.0),),
        )
        reversed_slip = self._make_natal_payslip("2026-12-31", "2026-12-31", 1400.0)
        with self.assertRaisesRegex(UserError, "backdated payment or a reversal"):
            reversed_slip.compute_sheet()

    def test_christmas_subsidy_monthly_duodecimos(self):
        """Opting in with the monthly input pays one twelfth of the
        annual entitlement each month with its proportional IRS
        withholding; a later lump settlement pays only the balance the
        installments left."""
        # January pays one twelfth of the 1400 entitlement; the hidden
        # helper stores the full basis for the withholding fraction.
        january = self._make_monthly_natal_payslip("2026-01-31", "2026-01-31")
        january.compute_sheet()
        lines = {line.code: line for line in january.line_ids}
        self.assertAlmostEqual(lines["PT_NATAL_MONTHLY_BASE"].total, 1400.0)
        self.assertFalse(lines["PT_NATAL_MONTHLY_BASE"].appears_on_payslip)
        self.assertAlmostEqual(lines["PT_NATAL_MONTHLY"].total, 116.67)
        self.assertAlmostEqual(lines["PT_NATAL_MONTHLY_IRS"].total, -23.33)
        self.assertAlmostEqual(lines["PT_SS_BASE"].total, 1516.67)
        self.assertAlmostEqual(lines["IRS"].total, -280.0)
        for absent in ("PT_NATAL", "PT_NATAL_CORRECTION", "PT_NATAL_IRS"):
            self.assertNotIn(absent, lines)
        january.action_payslip_done()
        self.assertEqual(january.state, "done")
        # A second January payslip for the same month pays nothing more.
        january_bis = self._make_monthly_natal_payslip("2026-01-31", "2026-01-31")
        january_bis.compute_sheet()
        bis_lines = {line.code: line for line in january_bis.line_ids}
        self.assertAlmostEqual(bis_lines["PT_NATAL_MONTHLY"].total, 0.0)
        self.assertNotIn("PT_NATAL_MONTHLY_IRS", bis_lines)
        # February continues the twelfths with the residual cent.
        february = self._make_monthly_natal_payslip("2026-02-28", "2026-02-28")
        february.compute_sheet()
        feb_lines = {line.code: line for line in february.line_ids}
        self.assertAlmostEqual(feb_lines["PT_NATAL_MONTHLY"].total, 116.66)
        self.assertAlmostEqual(feb_lines["PT_NATAL_MONTHLY_IRS"].total, -23.33)
        february.action_payslip_done()
        self.assertEqual(february.state, "done")
        # A December lump settlement pays only what the two finalized
        # installments left (1400 - 233.33) and withholds the matching
        # fraction of the annual subsidy tax.
        settlement = self._make_natal_payslip("2026-12-15", "2026-12-15", 1400.0)
        settlement.compute_sheet()
        settle_lines = {line.code: line for line in settlement.line_ids}
        self.assertAlmostEqual(settle_lines["PT_NATAL"].total, 1400.0)
        self.assertAlmostEqual(settle_lines["PT_NATAL_CORRECTION"].total, -233.33)
        self.assertAlmostEqual(settle_lines["PT_NATAL_IRS"].total, -233.33)
        self.assertAlmostEqual(settle_lines["GROSS"].total, 1166.67)

    def test_christmas_subsidy_monthly_full_year(self):
        """Twelve consecutive installments distribute the annual
        entitlement exactly, residual cents included."""
        month_ends = (
            "2026-01-31",
            "2026-02-28",
            "2026-03-31",
            "2026-04-30",
            "2026-05-31",
            "2026-06-30",
            "2026-07-31",
            "2026-08-31",
            "2026-09-30",
            "2026-10-31",
            "2026-11-30",
            "2026-12-31",
        )
        # Cumulative rounded twelfths of 1400: each month pays the
        # difference, so the cents land where the rounding needs them.
        expected = (
            116.67,
            116.66,
            116.67,
            116.67,
            116.66,
            116.67,
            116.67,
            116.66,
            116.67,
            116.67,
            116.66,
            116.67,
        )
        paid = 0.0
        for month, (date_to, scheduled) in enumerate(
            zip(month_ends, expected, strict=False), start=1
        ):
            with self.subTest(month=month):
                payslip = self._make_monthly_natal_payslip(date_to, date_to)
                payslip.compute_sheet()
                lines = {line.code: line for line in payslip.line_ids}
                self.assertAlmostEqual(lines["PT_NATAL_MONTHLY"].total, scheduled)
                paid += lines["PT_NATAL_MONTHLY"].total
                payslip.action_payslip_done()
                self.assertEqual(payslip.state, "done")
        self.assertAlmostEqual(paid, 1400.0)

    def test_christmas_subsidy_monthly_guards(self):
        """The monthly input cannot mix with the lump-sum input or the
        standalone structure, requires a Payment Date in the period
        year, and a late start pays only that month's installment."""
        # Both subsidy inputs on one regular payslip is rejected.
        mixed = self._make_payslip()
        mixed.payment_date = "2026-06-30"
        lump = mixed.input_line_ids.filtered(lambda line: line.code == "PT_NATAL")
        monthly = mixed.input_line_ids.filtered(
            lambda line: line.code == "PT_NATAL_MONTHLY"
        )
        self.assertEqual(len(lump), 1)
        self.assertEqual(len(monthly), 1)
        lump.amount = 1400.0
        monthly.amount = 1400.0
        with self.assertRaisesRegex(
            UserError, "only on a regular payslip without a lump-sum"
        ):
            mixed.compute_sheet()
        # The monthly input on the standalone Christmas structure is
        # rejected the same way.
        standalone = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2026-12-01",
                "date_to": "2026-12-31",
                "struct_id": self.env.ref("l10n_pt_payroll.structure_pt_natal").id,
            }
        )
        standalone.payment_date = "2026-12-15"
        standalone.onchange_employee()
        standalone_monthly = standalone.input_line_ids.filtered(
            lambda line: line.code == "PT_NATAL_MONTHLY"
        )
        self.assertEqual(len(standalone_monthly), 1)
        standalone_monthly.amount = 1400.0
        with self.assertRaisesRegex(
            UserError, "only on a regular payslip without a lump-sum"
        ):
            standalone.compute_sheet()
        # The monthly input requires a Payment Date in the period year.
        undated = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2026-11-01",
                "date_to": "2026-11-30",
            }
        )
        undated.onchange_employee()
        undated_monthly = undated.input_line_ids.filtered(
            lambda line: line.code == "PT_NATAL_MONTHLY"
        )
        self.assertEqual(len(undated_monthly), 1)
        undated_monthly.amount = 1400.0
        with self.assertRaisesRegex(UserError, "payment date"):
            undated.compute_sheet()
        # Starting the monthly payments in June pays only June's
        # installment — earlier months are not caught up.
        june = self._make_monthly_natal_payslip("2026-06-30", "2026-06-30")
        june.compute_sheet()
        june_lines = {line.code: line for line in june.line_ids}
        self.assertAlmostEqual(june_lines["PT_NATAL_MONTHLY"].total, 116.67)

    def test_holiday_subsidy_split_payment(self):
        """A cumulative target pays only up to the reviewed amount due:
        EUR 700 of a EUR 1,400 entitlement alongside the Christmas
        subsidy on a regular slip, nothing on a repeated target, and
        the remaining EUR 700 on a later holiday-only slip."""
        # June regular payslip: holiday target 700 of 1400 plus the
        # full Christmas subsidy — each subsidy keeps its own IRS.
        june = self._make_ferias_payslip(
            "2026-06-30", "2026-06-25", 1400.0, target=700.0
        )
        natal = june.input_line_ids.filtered(lambda line: line.code == "PT_NATAL")
        self.assertEqual(len(natal), 1)
        natal.amount = 1400.0
        june.compute_sheet()
        lines = {line.code: line for line in june.line_ids}
        self.assertAlmostEqual(lines["PT_FERIAS_BASE"].total, 1400.0)
        self.assertFalse(lines["PT_FERIAS_BASE"].appears_on_payslip)
        self.assertAlmostEqual(lines["PT_FERIAS"].total, 700.0)
        self.assertAlmostEqual(lines["PT_FERIAS_IRS"].total, -140.0)
        self.assertAlmostEqual(lines["PT_NATAL"].total, 1400.0)
        self.assertAlmostEqual(lines["PT_NATAL_IRS"].total, -280.0)
        self.assertAlmostEqual(lines["IRS"].total, -280.0)
        # The holiday subsidy stays out of the generic contribution
        # base and carries its own employee and employer lines.
        self.assertAlmostEqual(lines["PT_SS_BASE"].total, 2800.0)
        self.assertAlmostEqual(lines["SS"].total, -308.0)
        self.assertAlmostEqual(lines["SS_COMP"].total, 665.0)
        self.assertAlmostEqual(lines["PT_FERIAS_SS"].total, -77.0)
        self.assertAlmostEqual(lines["PT_FERIAS_SS_COMP"].total, 166.25)
        ferias_rule = self.env.ref("l10n_pt_payroll.hr_rule_pt_ferias")
        self.assertEqual(ferias_rule.l10n_pt_dmr_at_role, "income")
        self.assertEqual(ferias_rule.l10n_pt_dmr_code, "A3")
        self.assertEqual(ferias_rule.l10n_pt_ss_nature_code, "F")
        self.assertEqual(ferias_rule.l10n_pt_ss_contribution_base, "exclude")
        june.action_payslip_done()
        self.assertEqual(june.state, "done")
        # A repeated cumulative target pays nothing more.
        repeat = self._make_ferias_payslip(
            "2026-06-30",
            "2026-06-30",
            1400.0,
            target=700.0,
            standalone=True,
        )
        repeat.compute_sheet()
        repeat_lines = {line.code: line for line in repeat.line_ids}
        self.assertAlmostEqual(repeat_lines["PT_FERIAS"].total, 0.0)
        self.assertNotIn("PT_FERIAS_IRS", repeat_lines)
        self.assertNotIn("PT_FERIAS_SS", repeat_lines)
        self.assertNotIn("PT_FERIAS_SS_COMP", repeat_lines)
        # July standalone remainder: no target settles the full
        # entitlement less what was paid, under the July table set.
        self.env["hr.pt.irs.withholding.import"]._import_csv_data(
            CSV_HEADER
            + "2026-07-01,2026-07-31,continente,I,0,,10,0,0,0,,"
            + SET_VALUES
            + "\n"
        )
        july = self._make_ferias_payslip(
            "2026-07-31", "2026-07-31", 1400.0, standalone=True
        )
        july.compute_sheet()
        july_lines = {line.code: line for line in july.line_ids}
        self.assertAlmostEqual(july_lines["PT_FERIAS"].total, 700.0)
        self.assertAlmostEqual(july_lines["PT_FERIAS_IRS"].total, -70.0)
        self.assertAlmostEqual(july_lines["PT_FERIAS_SS"].total, -77.0)
        self.assertAlmostEqual(july_lines["PT_FERIAS_SS_COMP"].total, 166.25)
        self.assertAlmostEqual(july_lines["GROSS"].total, 700.0)
        for code in ("SS", "SS_COMP"):
            if code in july_lines:
                self.assertAlmostEqual(july_lines[code].total, 0.0)
        for absent in ("BASIC", "PT_NATAL", "PT_NATAL_IRS", "IRS"):
            self.assertNotIn(absent, july_lines)

    def test_holiday_subsidy_guards(self):
        """Invalid cumulative targets, a missing Payment Date, and
        Christmas inputs on a holiday-only slip are rejected."""
        # A cumulative target above the annual entitlement is refused.
        over = self._make_ferias_payslip(
            "2026-06-30", "2026-06-30", 1400.0, target=2000.0
        )
        with self.assertRaisesRegex(UserError, "exceeds the annual entitlement"):
            over.compute_sheet()
        # The holiday subsidy requires a Payment Date in the period year.
        undated = self._make_ferias_payslip("2026-11-30", None, 1400.0)
        with self.assertRaisesRegex(UserError, "payment date"):
            undated.compute_sheet()
        # A Christmas subsidy input on a holiday-only slip is refused.
        mixed = self._make_ferias_payslip(
            "2026-12-15", "2026-12-15", 1400.0, standalone=True
        )
        natal = mixed.input_line_ids.filtered(lambda line: line.code == "PT_NATAL")
        self.assertEqual(len(natal), 1)
        natal.amount = 1400.0
        with self.assertRaisesRegex(UserError, "holiday-only"):
            mixed.compute_sheet()
        # The monthly input cannot mix with the manual holiday inputs.
        mixed_monthly = self._make_ferias_payslip("2026-06-30", "2026-06-30", 1400.0)
        monthly = mixed_monthly.input_line_ids.filtered(
            lambda line: line.code == "PT_FERIAS_MONTHLY"
        )
        self.assertEqual(len(monthly), 1)
        monthly.amount = 1400.0
        with self.assertRaisesRegex(
            UserError, "monthly holiday subsidy only on a regular"
        ):
            mixed_monthly.compute_sheet()
        # The monthly input on the holiday-only structure is refused.
        standalone_monthly = self._make_ferias_monthly_payslip(
            "2026-12-15", "2026-12-15", standalone=True
        )
        with self.assertRaisesRegex(
            UserError, "monthly holiday subsidy only on a regular"
        ):
            standalone_monthly.compute_sheet()

    def test_holiday_subsidy_monthly_duodecimos(self):
        """Opting in with the monthly input pays one twelfth of the
        annual holiday entitlement each month; holiday contributions
        apply only to the installment paid and a manual settlement
        subtracts the installments already paid."""
        # January pays one twelfth; holiday Social Security applies
        # to the installment only, outside the ordinary base.
        january = self._make_ferias_monthly_payslip("2026-01-31", "2026-01-31")
        january.compute_sheet()
        lines = {line.code: line for line in january.line_ids}
        self.assertAlmostEqual(lines["PT_FERIAS_BASE"].total, 1400.0)
        self.assertAlmostEqual(lines["PT_FERIAS"].total, 116.67)
        self.assertAlmostEqual(lines["PT_FERIAS_IRS"].total, -23.33)
        self.assertAlmostEqual(lines["PT_FERIAS_SS"].total, -12.83)
        self.assertAlmostEqual(lines["PT_FERIAS_SS_COMP"].total, 27.71)
        self.assertAlmostEqual(lines["PT_SS_BASE"].total, 1400.0)
        january.action_payslip_done()
        self.assertEqual(january.state, "done")
        # A second January payslip for the same month pays nothing more.
        january_bis = self._make_ferias_monthly_payslip("2026-01-31", "2026-01-31")
        january_bis.compute_sheet()
        bis_lines = {line.code: line for line in january_bis.line_ids}
        self.assertAlmostEqual(bis_lines["PT_FERIAS"].total, 0.0)
        for absent in ("PT_FERIAS_IRS", "PT_FERIAS_SS", "PT_FERIAS_SS_COMP"):
            self.assertNotIn(absent, bis_lines)
        # February continues the twelfths with the residual cent.
        february = self._make_ferias_monthly_payslip("2026-02-28", "2026-02-28")
        february.compute_sheet()
        feb_lines = {line.code: line for line in february.line_ids}
        self.assertAlmostEqual(feb_lines["PT_FERIAS"].total, 116.66)
        february.action_payslip_done()
        self.assertEqual(february.state, "done")
        # A manual settlement pays only the balance the installments
        # left of the annual entitlement.
        settlement = self._make_ferias_payslip(
            "2026-12-15", "2026-12-15", 1400.0, standalone=True
        )
        settlement.compute_sheet()
        settle_lines = {line.code: line for line in settlement.line_ids}
        self.assertAlmostEqual(settle_lines["PT_FERIAS"].total, 1166.67)
        self.assertAlmostEqual(settle_lines["GROSS"].total, 1166.67)

    def test_holiday_subsidy_monthly_full_year(self):
        """Twelve consecutive monthly installments distribute the annual
        holiday entitlement exactly, residual cents included."""
        month_ends = (
            "2026-01-31",
            "2026-02-28",
            "2026-03-31",
            "2026-04-30",
            "2026-05-31",
            "2026-06-30",
            "2026-07-31",
            "2026-08-31",
            "2026-09-30",
            "2026-10-31",
            "2026-11-30",
            "2026-12-31",
        )
        expected = (
            116.67,
            116.66,
            116.67,
            116.67,
            116.66,
            116.67,
            116.67,
            116.66,
            116.67,
            116.67,
            116.66,
            116.67,
        )
        paid = 0.0
        for month, (date_to, scheduled) in enumerate(
            zip(month_ends, expected, strict=False), start=1
        ):
            with self.subTest(month=month):
                payslip = self._make_ferias_monthly_payslip(date_to, date_to)
                payslip.compute_sheet()
                lines = {line.code: line for line in payslip.line_ids}
                self.assertAlmostEqual(lines["PT_FERIAS"].total, scheduled)
                paid += lines["PT_FERIAS"].total
                payslip.action_payslip_done()
                self.assertEqual(payslip.state, "done")
        self.assertAlmostEqual(paid, 1400.0)

    def test_irs_retention_no_table(self):
        """A payslip outside every imported table period fails loudly
        instead of silently using a stale rate."""
        payslip = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2027-06-01",
                "date_to": "2027-06-30",
            }
        )
        payslip.onchange_employee()
        with self.assertRaises(UserError):
            payslip.compute_sheet()

    def test_payment_method_is_versioned_and_inert(self):
        """The salary payment method lives on the contract version: it
        starts unset, an employee write updates the current version, a
        dated version change preserves earlier values, and none of it
        touches bank accounts."""
        employee = self.env["hr.employee"].create(
            {
                "name": "Payment Method Employee",
                "company_id": self.env.company.id,
                "date_version": "2026-01-01",
            }
        )
        version = employee.version_id
        self.assertFalse(version.l10n_pt_payment_method)
        self.assertFalse(employee.bank_account_ids)

        employee.write({"l10n_pt_payment_method": "cheque"})
        self.assertEqual(version.l10n_pt_payment_method, "cheque")
        self.assertFalse(employee.bank_account_ids)

        new_version = employee.create_version(
            {
                "date_version": "2026-11-01",
                "l10n_pt_payment_method": "cash",
            }
        )
        self.assertNotEqual(new_version, version)
        self.assertEqual(new_version.l10n_pt_payment_method, "cash")
        self.assertEqual(
            employee._get_version("2026-10-31").l10n_pt_payment_method,
            "cheque",
        )
        self.assertFalse(employee.bank_account_ids)

    def test_payment_method_id_is_versioned_and_validated(self):
        """The Accounting payment method lives on the contract version
        next to the legacy selection: it starts unset, an employee
        write updates the current version, a dated version change can
        clear it while earlier dates keep theirs, and only outbound
        methods are accepted."""
        employee = self.env["hr.employee"].create(
            {
                "name": "Payment Method Id Employee",
                "company_id": self.env.company.id,
                "date_version": "2026-01-01",
                "l10n_pt_payment_method": "cheque",
            }
        )
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        version = employee.version_id
        self.assertFalse(employee.payment_method_id)
        self.assertEqual(employee.l10n_pt_payment_method, "cheque")
        self.assertFalse(employee.bank_account_ids)

        employee.write({"payment_method_id": manual_out.id})
        self.assertEqual(version.payment_method_id, manual_out)
        self.assertEqual(employee.l10n_pt_payment_method, "cheque")
        self.assertFalse(employee.bank_account_ids)

        new_version = employee.create_version(
            {
                "date_version": "2026-11-01",
                "payment_method_id": False,
            }
        )
        self.assertNotEqual(new_version, version)
        self.assertFalse(new_version.payment_method_id)
        self.assertEqual(
            employee._get_version("2026-10-31").payment_method_id,
            manual_out,
        )
        self.assertFalse(employee.bank_account_ids)

        with self.assertRaises(ValidationError):
            employee.version_id.write({"payment_method_id": manual_in.id})

    def _make_history_slip(
        self,
        date_to,
        payment_date=None,
        state="done",
        credit_note=False,
        employee=None,
        company=None,
        contract=None,
        lines=(),
    ):
        """Record a payslip ledger entry with known line totals, without
        running payroll computation, for payroll-history tests."""
        employee = employee or self.employee
        contract = contract or employee.version_id
        slip = self.env["hr.payslip"].create(
            {
                "employee_id": employee.id,
                "company_id": (company or self.env.company).id,
                "contract_id": contract.id,
                "date_from": f"{date_to[:7]}-01",
                "date_to": date_to,
                "payment_date": payment_date,
                "state": state,
                "credit_note": credit_note,
            }
        )
        for code, total in lines:
            rule = self.env.ref(_HISTORY_RULE_XMLIDS[code])
            self.env["hr.payslip.line"].create(
                {
                    "slip_id": slip.id,
                    "salary_rule_id": rule.id,
                    "employee_id": employee.id,
                    "contract_id": contract.id,
                    "code": code,
                    "name": rule.name,
                    "category_id": rule.category_id.id,
                    "sequence": rule.sequence,
                    "appears_on_payslip": rule.appears_on_payslip,
                    "amount": total,
                    "quantity": 1.0,
                    "rate": 100.0,
                }
            )
        return slip

    def test_payroll_history_totals_windows(self):
        """The documented history helper separates payment-date windows
        from period windows, excludes unfinished or foreign slips, nets
        finalized reversals, and aggregates across contract versions."""
        # A contract version change in October 2026: history must still
        # aggregate payslips recorded under either version.
        self.employee.version_id.contract_date_end = "2026-09-30"
        version2 = self.employee.version_id.copy(
            {
                "date_version": "2026-10-01",
                "contract_date_start": "2026-10-01",
                "contract_date_end": False,
                "wage": 1500.0,
            }
        )
        other_employee = self.env["hr.employee"].create(
            {"name": "Other Employee", "company_id": self.env.company.id}
        )
        other_company = self.env["res.company"].create({"name": "Other Company"})

        # Finalized ledger entries around the year boundary. December
        # work paid in January counts for payment-date windows anchored
        # in January but not for the rolling window ending in December.
        self._make_history_slip("2026-10-31", lines=(("GROSS", 1000.0),))
        self._make_history_slip(
            "2026-10-31", credit_note=True, lines=(("GROSS", 1000.0),)
        )
        self._make_history_slip(
            "2026-11-30",
            payment_date="2026-11-30",
            lines=(("GROSS", 2000.0),),
        )
        self._make_history_slip(
            "2026-12-31",
            payment_date="2027-01-10",
            contract=version2,
            lines=(("GROSS", 3000.0), ("IRS", -280.0)),
        )
        self._make_history_slip(
            "2026-12-31",
            payment_date="2027-01-20",
            contract=version2,
            lines=(("GROSS", 4000.0), ("IRS", -640.0)),
        )
        self._make_history_slip(
            "2026-12-31",
            payment_date="2027-02-05",
            contract=version2,
            lines=(("GROSS", 7000.0),),
        )
        self._make_history_slip(
            "2027-01-05",
            payment_date="2027-01-08",
            contract=version2,
            lines=(("GROSS", 600.0), ("IRS", -120.0)),
        )
        # Entries that must not count: drafts, cancelled slips, another
        # employee and another employer.
        self._make_history_slip(
            "2026-11-15",
            payment_date="2026-11-20",
            state="draft",
            lines=(("GROSS", 5000.0),),
        )
        self._make_history_slip(
            "2026-11-10",
            payment_date="2026-11-25",
            state="cancel",
            lines=(("GROSS", 6000.0),),
        )
        self._make_history_slip(
            "2026-10-31",
            employee=other_employee,
            lines=(("GROSS", 9000.0),),
        )
        self._make_history_slip(
            "2026-10-31",
            company=other_company,
            lines=(("GROSS", 8000.0),),
        )

        anchor = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "company_id": self.env.company.id,
                "contract_id": version2.id,
                "date_from": "2027-01-01",
                "date_to": "2027-01-15",
                "payment_date": "2027-01-15",
            }
        )
        totals = anchor._get_payroll_history_totals
        expected = {
            "GROSS": 3600.0,
            "IRS": -400.0,
            "MISSING": 0.0,
        }
        for window in ("year_to_date", "month_to_date"):
            with self.subTest(date_basis="payment", window=window):
                self.assertEqual(
                    totals(
                        ("GROSS", "IRS", "MISSING"),
                        date_basis="payment",
                        window=window,
                    ),
                    expected,
                )
        self.assertEqual(
            totals(
                ("GROSS", "IRS", "MISSING"),
                date_basis="payment",
                window="previous_months",
                months=3,
            ),
            {"GROSS": 2000.0, "IRS": 0.0, "MISSING": 0.0},
        )
        for window in ("year_to_date", "month_to_date"):
            with self.subTest(date_basis="period", window=window):
                self.assertEqual(
                    totals(
                        ("GROSS", "IRS", "MISSING"),
                        date_basis="period",
                        window=window,
                    ),
                    {"GROSS": 600.0, "IRS": -120.0, "MISSING": 0.0},
                )
        self.assertEqual(
            totals(
                ("GROSS", "IRS", "MISSING"),
                date_basis="period",
                window="previous_months",
                months=3,
            ),
            {"GROSS": 16000.0, "IRS": -920.0, "MISSING": 0.0},
        )
        # Invalid arguments are rejected loudly for rule authors.
        with self.assertRaises(ValueError):
            totals(("GROSS",), date_basis="bogus", window="year_to_date")
        with self.assertRaises(ValueError):
            totals(("GROSS",), date_basis="payment", window="bogus")
        with self.assertRaises(ValueError):
            totals(("GROSS",), date_basis="payment", window="previous_months")
        with self.assertRaises(ValueError):
            totals(
                ("GROSS",),
                date_basis="payment",
                window="previous_months",
                months=0,
            )
        with self.assertRaises(ValueError):
            totals(
                ("GROSS",),
                date_basis="payment",
                window="year_to_date",
                months=3,
            )

    def test_payroll_history_totals_in_salary_rule(self):
        """A custom salary rule can consume the documented history helper
        inside the payroll compute."""
        # A 2027 table lets the January payslip compute its own IRS.
        self.env["hr.pt.irs.withholding.import"]._import_csv_data(
            CSV_HEADER
            + "".join(
                f"2027-01-01,2027-12-31,continente,{code},{lower},{upper},"
                f"{rate},{parcela},30,0,,{SET_VALUES}\n"
                for code in ("I", "II", "III")
                for lower, upper, rate, parcela in (
                    ("0", "2000", "20", "0"),
                    ("2000", "", "40", "200"),
                )
            )
        )
        rule = self.env["hr.salary.rule"].create(
            {
                "name": "History YTD",
                "code": "HT_YTD",
                "sequence": 490,
                "category_id": self.env.ref(
                    "l10n_pt_payroll.categ_pt_irs_reference"
                ).id,
                "appears_on_payslip": False,
                "condition_select": "none",
                "amount_select": "code",
                "amount_python_compute": (
                    "result = payslip._get_payroll_history_totals("
                    "('GROSS',), date_basis='payment', "
                    "window='year_to_date')['GROSS']"
                ),
            }
        )
        self.structure.rule_ids = [Command.link(rule.id)]

        # December work paid in January counts; last November's payment
        # stays outside the payment-date year-to-date window.
        self._make_history_slip(
            "2026-11-30",
            payment_date="2026-11-30",
            lines=(("GROSS", 2000.0),),
        )
        self._make_history_slip(
            "2026-12-31",
            payment_date="2027-01-10",
            lines=(("GROSS", 3000.0),),
        )
        self._make_history_slip(
            "2027-01-05",
            payment_date="2027-01-08",
            lines=(("GROSS", 600.0),),
        )

        payslip = self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "date_from": "2027-01-01",
                "date_to": "2027-01-15",
                "payment_date": "2027-01-15",
            }
        )
        payslip.onchange_employee()
        payslip.compute_sheet()

        history = payslip.line_ids.filtered(lambda line: line.code == "HT_YTD")
        self.assertEqual(len(history), 1)
        self.assertEqual(history.total, 3600.0)


class TestL10nPtSalaryBankAccount(TransactionCase):
    """The salary bank account lives on the contract version: an HR
    manager picks one of the employee's standard bank accounts, invalid
    or foreign accounts are rejected, history is preserved, and the Add
    Bank Account wizard creates, links, and selects a new account on the
    employee's work contact."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Salary Bank Employee",
                "company_id": cls.env.company.id,
                "date_version": "2026-01-01",
            }
        )
        contact = cls.employee.work_contact_id
        cls.account_primary = cls.env["res.partner.bank"].create(
            {
                "partner_id": contact.id,
                "acc_number": "PT50000000000000000000001",
            }
        )
        cls.account_secondary = cls.env["res.partner.bank"].create(
            {
                "partner_id": contact.id,
                "acc_number": "PT50000000000000000000002",
            }
        )
        cls.account_unlinked = cls.env["res.partner.bank"].create(
            {
                "partner_id": contact.id,
                "acc_number": "PT50000000000000000000003",
            }
        )
        other_partner = cls.env["res.partner"].create({"name": "Other Owner"})
        cls.account_foreign = cls.env["res.partner.bank"].create(
            {
                "partner_id": other_partner.id,
                "acc_number": "PT50000000000000000000004",
            }
        )
        cls.employee.write(
            {
                "bank_account_ids": [
                    Command.link(cls.account_primary.id),
                    Command.link(cls.account_secondary.id),
                ]
            }
        )

    def _hr_manager(self, with_partner_manager=True):
        groups = [
            self.env.ref("base.group_user"),
            self.env.ref("hr.group_hr_manager"),
        ]
        if with_partner_manager:
            groups.append(self.env.ref("base.group_partner_manager"))
        return self.env["res.users"].create(
            {
                "name": "Salary Bank HR Manager",
                "login": f"salary_bank_hr_manager_{with_partner_manager}",
                "company_id": self.env.company.id,
                "company_ids": [Command.set([self.env.company.id])],
                "group_ids": [Command.set(group.id for group in groups)],
            }
        )

    def test_payment_bank_account_is_versioned_and_inert(self):
        """An employee write selects the account on the current version,
        a dated version change keeps earlier selections, and archiving
        or unlinking an account never clears stored history."""
        employee = self.employee
        version = employee.version_id
        self.assertFalse(employee.payment_bank_account_id)

        employee.write({"payment_bank_account_id": self.account_primary.id})
        self.assertEqual(version.payment_bank_account_id, self.account_primary)
        self.assertEqual(employee.payment_bank_account_id, self.account_primary)

        new_version = employee.create_version(
            {
                "date_version": "2026-11-01",
                "payment_bank_account_id": self.account_secondary.id,
            }
        )
        self.assertNotEqual(new_version, version)
        self.assertEqual(new_version.payment_bank_account_id, self.account_secondary)
        self.assertEqual(
            employee._get_version("2026-10-31").payment_bank_account_id,
            self.account_primary,
        )

        self.account_primary.write({"active": False})
        self.assertFalse(self.account_primary.active)
        self.assertEqual(
            employee._get_version("2026-10-31").payment_bank_account_id,
            self.account_primary,
        )

        employee.write({"bank_account_ids": [Command.unlink(self.account_primary.id)]})
        self.assertEqual(
            employee._get_version("2026-10-31").payment_bank_account_id,
            self.account_primary,
        )

    def test_payment_bank_account_rejects_invalid_accounts(self):
        """ORM writes reject a same-contact account missing from the
        employee's Bank Accounts and an account owned by another
        partner, bypassing the view domain."""
        with self.assertRaises(ValidationError):
            self.employee.write({"payment_bank_account_id": self.account_unlinked.id})
        with self.assertRaises(ValidationError):
            self.employee.write({"payment_bank_account_id": self.account_foreign.id})
        self.assertFalse(self.employee.payment_bank_account_id)

    def test_add_bank_account_wizard(self):
        """The Add Bank Account wizard, bound to a version, creates a
        standard account on the work contact, links it to the employee,
        selects it on that version, and keeps the existing bank
        accounts untouched."""
        hr_manager = self._hr_manager()
        employee = self.employee
        version = employee.version_id
        previous_accounts = employee.bank_account_ids

        blank_wizard = (
            self.env["hr.payroll.bank.account.add"]
            .with_user(hr_manager)
            .with_context(default_version_id=version.id)
            .create({"acc_number": "   "})
        )
        with self.assertRaises(UserError):
            blank_wizard.action_add_bank_account()

        wizard = (
            self.env["hr.payroll.bank.account.add"]
            .with_user(hr_manager)
            .with_context(default_version_id=version.id)
            .create({"acc_number": "PT50000000000000000000009"})
        )
        result = wizard.with_context(
            default_allow_out_payment=True
        ).action_add_bank_account()
        self.assertEqual(result["tag"], "soft_reload")

        self.env.invalidate_all()
        employee = self.env["hr.employee"].browse(employee.id)
        version = employee.version_id
        account = employee.work_contact_id.bank_ids.filtered(
            lambda bank: bank.acc_number == "PT50000000000000000000009"
        )
        self.assertEqual(len(account), 1)
        self.assertFalse(account.allow_out_payment)
        self.assertIn(account, employee.bank_account_ids)
        self.assertTrue(previous_accounts <= employee.bank_account_ids)
        self.assertEqual(version.payment_bank_account_id, account)
        self.assertEqual(employee.payment_bank_account_id, account)

    def test_add_bank_account_wizard_requires_rights(self):
        """Only HR managers can use the employee action, and creating
        the bank account still needs native Partner Creation rights."""
        plain_user = self.env["res.users"].create(
            {
                "name": "Plain Internal User",
                "login": "salary_bank_plain_user",
                "company_id": self.env.company.id,
                "company_ids": [Command.set([self.env.company.id])],
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            self.employee.with_user(plain_user).action_add_payment_bank_account()

        hr_only = self._hr_manager(with_partner_manager=False)
        wizard = (
            self.env["hr.payroll.bank.account.add"]
            .with_user(hr_only)
            .with_context(default_version_id=self.employee.version_id.id)
            .create({"acc_number": "PT50000000000000000000010"})
        )
        with self.assertRaises(AccessError):
            wizard.action_add_bank_account()

    def test_add_bank_account_button_native_form(self):
        """The Add Bank Account shortcut opens the same dedicated bank
        form as the selector and, through its context, selects the new
        account on the version immediately."""
        hr_manager = self._hr_manager()
        employee = self.employee
        version = employee.version_id
        contact = employee.work_contact_id
        bank = self.env["res.bank"].search([], limit=1) or self.env["res.bank"].create(
            {"name": "Selector Test Bank"}
        )

        action = employee.with_user(hr_manager).action_add_payment_bank_account()
        bank_view = self.env.ref("l10n_pt_payroll.view_payroll_partner_bank_form")
        self.assertEqual(action["res_model"], "res.partner.bank")
        self.assertEqual(action["views"], [(bank_view.id, "form")])
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_partner_id"], contact.id)
        self.assertEqual(
            action["context"]["payroll_bank_account_version_id"], version.id
        )
        self.assertTrue(action["context"]["payroll_select_bank_account"])

        account = (
            self.env["res.partner.bank"]
            .with_user(hr_manager)
            .with_context(**action["context"])
            .create(
                {
                    "partner_id": contact.id,
                    "acc_number": "PT50000000000000000000015",
                    "bank_id": bank.id,
                }
            )
        )
        self.env.invalidate_all()
        employee = self.env["hr.employee"].browse(employee.id)
        version = employee.version_id
        self.assertEqual(account.partner_id, contact)
        self.assertEqual(account.bank_id, bank)
        self.assertIn(account.id, employee.bank_account_ids.ids)
        self.assertEqual(version.payment_bank_account_id, account)
        self.assertEqual(employee.payment_bank_account_id, account)

    def test_bank_account_selector_native_create(self):
        """The Salary Bank Account selector's Create dialog goes through
        res.partner.bank.create with the payroll context: the account is
        pinned to the employee's work contact, never trusted, joins the
        contact and employee bank lists, and the stored version
        selection only changes when the employee form is saved."""
        hr_manager = self._hr_manager()
        employee = self.employee
        version = employee.version_id
        contact = employee.work_contact_id
        employee.write({"payment_bank_account_id": self.account_primary.id})

        account = (
            self.env["res.partner.bank"]
            .with_user(hr_manager)
            .with_context(
                default_partner_id=contact.id,
                payroll_bank_account_version_id=version.id,
            )
            .create(
                {
                    "partner_id": self.account_foreign.partner_id.id,
                    "acc_number": "PT50000000000000000000011",
                    "allow_out_payment": True,
                }
            )
        )
        self.env.invalidate_all()
        employee = self.env["hr.employee"].browse(employee.id)
        version = employee.version_id
        contact = employee.work_contact_id
        self.assertEqual(account.partner_id, contact)
        self.assertTrue(account.active)
        self.assertFalse(account.allow_out_payment)
        self.assertIn(account.id, contact.bank_ids.ids)
        self.assertIn(account.id, employee.bank_account_ids.ids)
        # Creating from the dialog does not select the account by itself.
        self.assertEqual(version.payment_bank_account_id, self.account_primary)

        employee.write({"payment_bank_account_id": account.id})
        self.assertEqual(version.payment_bank_account_id, account)

        # Without the payroll context, creation stays a plain bank account.
        plain_account = self.env["res.partner.bank"].create(
            {"partner_id": contact.id, "acc_number": "PT50000000000000000000012"}
        )
        self.assertNotIn(plain_account.id, employee.bank_account_ids.ids)

        # Users outside the payroll flow cannot use the context flag.
        plain_user = self.env["res.users"].create(
            {
                "name": "Plain Internal User Native",
                "login": "salary_bank_plain_user_native",
                "company_id": self.env.company.id,
                "company_ids": [Command.set([self.env.company.id])],
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            (
                self.env["res.partner.bank"]
                .with_user(plain_user)
                .with_context(payroll_bank_account_version_id=version.id)
                .create(
                    {
                        "partner_id": contact.id,
                        "acc_number": "PT50000000000000000000013",
                    }
                )
            )
        hr_only = self._hr_manager(with_partner_manager=False)
        with self.assertRaises(AccessError):
            (
                self.env["res.partner.bank"]
                .with_user(hr_only)
                .with_context(payroll_bank_account_version_id=version.id)
                .create(
                    {
                        "partner_id": contact.id,
                        "acc_number": "PT50000000000000000000014",
                    }
                )
            )

    def test_salary_bank_account_selector_view(self):
        """The Salary Bank Account field opens the dedicated bank form
        in create/edit dialogs and stays read-only until the employee
        has a saved record with a work contact."""
        arch = self.env.ref(
            "l10n_pt_payroll.view_employee_form_l10n_pt_payroll"
        ).get_combined_arch()
        root = ET.fromstring(arch)
        node = root.find(".//field[@name='payment_bank_account_id']")
        self.assertIsNotNone(node)
        self.assertEqual(node.get("readonly"), "not id or not work_contact_id")
        context = node.get("context") or ""
        self.assertIn("payroll_bank_account_version_id", context)
        self.assertIn("form_view_ref", context)
        self.assertIn("l10n_pt_payroll.view_payroll_partner_bank_form", context)
        options = node.get("options") or ""
        self.assertIn("no_quick_create", options)
        self.assertIn("no_open", options)
        self.assertNotIn("'no_create'", options)

        bank_view = self.env.ref("l10n_pt_payroll.view_payroll_partner_bank_form")
        self.assertEqual(bank_view.model, "res.partner.bank")
        self.assertEqual(bank_view.priority, 100)
        default_view = self.env["ir.ui.view"].search(
            [("model", "=", "res.partner.bank"), ("type", "=", "form")],
            order="priority, id",
            limit=1,
        )
        self.assertNotEqual(default_view, bank_view)


class TestL10nPtPayrollIrs(TransactionCase):
    def test_irs_table_derivation(self):
        """The IRS withholding table variant is derived from the declared
        determinants: family situation, IRS dependents and disability."""
        employee = self.env["hr.employee"].create(
            {
                "name": "IRS Employee 1",
                "l10n_pt_irs_family_status": "married_single_income",
            }
        )
        self.assertEqual(
            employee.l10n_pt_irs_table_id,
            self.env.ref("l10n_pt_hr.l10n_pt_irs_table_3"),
        )
        # Disability >= 60% switches to the disabled table variant
        employee.l10n_pt_disability_degree = 65
        self.assertEqual(
            employee.l10n_pt_irs_table_id,
            self.env.ref("l10n_pt_hr.l10n_pt_irs_table_7"),
        )
        # A single worker with dependents uses table II
        employee.write(
            {
                "l10n_pt_irs_family_status": "single",
                "l10n_pt_disability_degree": 0,
                "l10n_pt_irs_dependents": 2,
            }
        )
        self.assertEqual(
            employee.l10n_pt_irs_table_id,
            self.env.ref("l10n_pt_hr.l10n_pt_irs_table_2"),
        )
        # Without a declared family situation no table applies
        employee.l10n_pt_irs_family_status = False
        self.assertFalse(employee.l10n_pt_irs_table_id)

    def test_irs_table_derivation_pensioner(self):
        """A pensioner resolves the pension table family (VIII-XI),
        which only distinguishes family situation and disability — not
        dependents."""
        employee = self.env["hr.employee"].create(
            {
                "name": "Pensioner Employee",
                "l10n_pt_irs_pensioner": True,
                "l10n_pt_irs_family_status": "single",
                "l10n_pt_irs_dependents": 3,
            }
        )
        self.assertEqual(
            employee.l10n_pt_irs_table_id,
            self.env.ref("l10n_pt_hr.l10n_pt_irs_table_8"),
        )
        # Disabled pensioner with a single-income spouse uses table XI
        employee.write(
            {
                "l10n_pt_irs_family_status": "married_single_income",
                "l10n_pt_disability_degree": 70,
            }
        )
        self.assertEqual(
            employee.l10n_pt_irs_table_id,
            self.env.ref("l10n_pt_hr.l10n_pt_irs_table_11"),
        )
        # Non-pensioner with the same determinants uses the work tables
        employee.l10n_pt_irs_pensioner = False
        self.assertEqual(
            employee.l10n_pt_irs_table_id,
            self.env.ref("l10n_pt_hr.l10n_pt_irs_table_7"),
        )

    def test_irs_region_from_address(self):
        """The IRS region defaults from the employee's address: PT state
        districts first, postal code prefix as fallback, and a manual
        choice is kept."""
        employee = self.env["hr.employee"].create(
            {
                "name": "IRS Employee 2",
                "private_state_id": self.env.ref("base.state_pt_pt-20").id,
            }
        )
        self.assertEqual(employee.l10n_pt_irs_region, "acores")
        employee.private_state_id = self.env.ref("base.state_pt_pt-30")
        # region was auto-filled once; a manual value wins over recompute
        self.assertEqual(employee.l10n_pt_irs_region, "acores")
        employee.l10n_pt_irs_region = "madeira"
        employee.private_zip = "4000-001"
        self.assertEqual(employee.l10n_pt_irs_region, "madeira")


class TestL10nPtPayrollIrsImport(TransactionCase):
    def test_import_csv_creates_table_sets(self):
        """A valid CSV creates one withholding table set per
        (period, region, variant) block with its brackets."""
        # 2030 keeps the fixture clear of the bundled 2026 tables.
        csv_text = CSV_HEADER + (
            "2030-01-01,2030-12-31,acores,I,0,1500,18,0,30,50,,522.50\n"
            "2030-01-01,2030-12-31,acores,I,1500,,40,200,30,50,,522.50\n"
            "2030-01-01,2030-12-31,madeira,II,0,,25,100,30,50,,522.50\n"
        )
        count = self.env["hr.pt.irs.withholding.import"]._import_csv_data(csv_text)
        self.assertEqual(count, 2)
        tables = self.env["hr.pt.irs.withholding.table"].search(
            [
                ("region", "in", ["acores", "madeira"]),
                ("date_start", "=", "2030-01-01"),
            ]
        )
        self.assertEqual(len(tables), 2)
        acores = tables.filtered(lambda t: t.region == "acores")
        self.assertEqual(len(acores.line_ids), 2)
        self.assertAlmostEqual(acores.ias, 522.50)

    def test_import_csv_replaces_existing_lines(self):
        """Re-importing the same block replaces its brackets instead of
        duplicating them."""
        # 2030 keeps the fixture clear of the bundled 2026 tables.
        csv_text = CSV_HEADER + (
            "2030-01-01,2030-12-31,continente,I,0,,20,0,0,0,,522.50\n"
        )
        model = self.env["hr.pt.irs.withholding.import"]
        model._import_csv_data(csv_text)
        corrected = csv_text.replace(",20,0,0,0,", ",22.5,0,0,0,")
        model._import_csv_data(corrected)
        table = self.env["hr.pt.irs.withholding.table"].search(
            [
                ("region", "=", "continente"),
                ("table_id", "=", self.env.ref("l10n_pt_hr.l10n_pt_irs_table_1").id),
            ],
            limit=1,
        )
        self.assertEqual(len(table.line_ids), 1)
        self.assertAlmostEqual(table.line_ids.marginal_rate, 22.5)

    def test_import_csv_validation_errors(self):
        """Invalid files are rejected: gaps in the brackets, unknown
        regions or table codes, out-of-range rates."""
        model = self.env["hr.pt.irs.withholding.import"]
        with self.assertRaises(UserError):
            # Gap between brackets
            model._import_csv_data(
                CSV_HEADER
                + "2026-01-01,2026-12-31,continente,I,0,1000,20,0,0,0,,1\n"
                + "2026-01-01,2026-12-31,continente,I,2000,,40,0,0,0,,1\n"
            )
        with self.assertRaises(UserError):
            # Unknown region
            model._import_csv_data(
                CSV_HEADER + "2026-01-01,2026-12-31,atlantico,I,0,,20,0,0,0,,1\n"
            )
        with self.assertRaises(UserError):
            # Rate above 100
            model._import_csv_data(
                CSV_HEADER + "2026-01-01,2026-12-31,continente,I,0,,150,0,0,0,,1\n"
            )
        with self.assertRaises(UserError):
            # Missing required column
            model._import_csv_data(
                "date_start,region,table_code\n2026-01-01,continente,I\n"
            )
