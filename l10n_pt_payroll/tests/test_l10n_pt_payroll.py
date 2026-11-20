# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

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
        exempts 50% of the income up to 55 x IAS."""
        self.employee.write(
            {
                "l10n_pt_irs_jovem": True,
                "l10n_pt_irs_income_years": 4,  # 5th year -> 50%
            }
        )
        payslip = self._make_payslip()
        payslip.compute_sheet()
        lines = {line.code: line.total for line in payslip.line_ids}
        # exempt = min(1400, 55*522.50) * 0.5 = 700 -> base = 700
        # 700 * 20% = 140
        self.assertAlmostEqual(lines["IRS"], -140.0)

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
