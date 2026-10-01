# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.fields import Date
from odoo.tests.common import TransactionCase


class TestL10nPtPayroll(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Payslip = self.env["hr.payslip"]
        self.structure = self.env.ref("l10n_pt_payroll.structure_pt")
        self.employee = self.env["hr.employee"].create(
            {
                "name": "Test Employee",
                "company_id": self.env.company.id,
            }
        )
        # Initialize the contract (hr.version) created at employee creation
        first_day = Date.today().strftime("%Y-%m-01")
        self.employee.version_id.write(
            {
                "contract_date_start": first_day,
                "contract_date_end": False,
                "wage": 1400.0,
                "struct_id": self.structure.id,
                "resource_calendar_id": self.env.company.resource_calendar_id.id,
            }
        )

    def test_pt_payroll_structure(self):
        self.assertEqual(self.structure.code, "PT")
        self.assertTrue(
            {"BASIC", "SA", "GROSS", "SS", "IRS", "SS_COMP", "NET"}
            <= set(self.structure.rule_ids.mapped("code"))
        )

    def test_pt_payslip_compute(self):
        payslip = self.Payslip.create({"employee_id": self.employee.id})
        payslip.onchange_employee()
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
        self.assertAlmostEqual(lines["BASIC"], 1400.0)
        self.assertAlmostEqual(lines["SA"], meal)
        self.assertAlmostEqual(lines["GROSS"], 1400.0 + meal)
        self.assertAlmostEqual(lines["SS"], -0.11 * 1400.0)
        self.assertAlmostEqual(lines["IRS"], -0.15 * 1400.0)
        self.assertAlmostEqual(lines["SS_COMP"], 0.2375 * 1400.0)
        self.assertAlmostEqual(
            lines["NET"], 1400.0 + meal - 0.11 * 1400.0 - 0.15 * 1400.0
        )
