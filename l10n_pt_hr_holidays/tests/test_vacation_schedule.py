# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import date

from lxml import html

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user
from odoo.tools import format_date


class TestVacationSchedule(TransactionCase):
    """Feature coverage for the printable annual vacation schedule."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pt = cls.env.ref("base.pt")
        cls.us = cls.env.ref("base.us")
        cls.company_a = cls.env["res.company"].create(
            {"name": "Schedule Company A", "country_id": cls.pt.id}
        )
        cls.company_b = cls.env["res.company"].create(
            {"name": "Schedule Company B", "country_id": cls.pt.id}
        )
        cls.company_us = cls.env["res.company"].create(
            {"name": "Schedule Company US", "country_id": cls.us.id}
        )
        cls.manager = new_test_user(
            cls.env,
            login="vacation_schedule_manager",
            groups="hr_holidays.group_hr_holidays_manager",
            company_id=cls.company_a.id,
            company_ids=[
                Command.set([cls.company_a.id, cls.company_b.id, cls.company_us.id])
            ],
            lang="en_US",
        )
        cls.plain_user = new_test_user(
            cls.env,
            login="vacation_schedule_user",
            groups="base.group_user",
            company_id=cls.company_a.id,
            company_ids=[Command.set([cls.company_a.id, cls.company_b.id])],
            lang="en_US",
        )
        cls.annual_leave = cls.env.ref("l10n_pt_hr_holidays.leave_type_annual_leave")
        cls.sick_leave = cls.env.ref(
            "l10n_pt_hr_holidays.leave_type_non_occupational_illness"
        )
        cls.alex = cls._create_employee("Alex Vacation", cls.company_a)
        cls.pending_employee = cls._create_employee("Pending Employee", cls.company_a)
        cls.absence_employee = cls._create_employee("Absence Employee", cls.company_a)
        cls.other_company_employee = cls._create_employee(
            "Other Company Employee", cls.company_b
        )
        cls.unassigned_employee = cls._create_employee(
            "Unassigned Employee", cls.company_a
        )
        for employee in (
            cls.alex,
            cls.pending_employee,
            cls.other_company_employee,
            cls.unassigned_employee,
        ):
            cls._create_allocation(employee)
        cls._create_leave(
            cls.alex,
            cls.annual_leave,
            date(2025, 12, 29),
            date(2026, 1, 2),
            "Private vacation note",
        )
        cls._create_leave(
            cls.alex,
            cls.annual_leave,
            date(2026, 6, 8),
            date(2026, 6, 12),
            "Private vacation note",
        )
        cls._create_leave(
            cls.pending_employee,
            cls.annual_leave,
            date(2026, 7, 6),
            date(2026, 7, 10),
            "Private vacation note",
            approve=False,
        )
        cls._create_leave(
            cls.absence_employee,
            cls.sick_leave,
            date(2026, 7, 13),
            date(2026, 7, 17),
            "Private sickness note",
        )
        cls._create_leave(
            cls.other_company_employee,
            cls.annual_leave,
            date(2026, 6, 8),
            date(2026, 6, 12),
            "Private vacation note",
        )
        cls._create_leave(
            cls.unassigned_employee,
            cls.annual_leave,
            date(2026, 9, 1),
            date(2026, 9, 4),
            "Private vacation note",
        )

    @classmethod
    def _create_employee(cls, name, company):
        return cls.env["hr.employee"].create({"name": name, "company_id": company.id})

    @classmethod
    def _create_allocation(cls, employee):
        allocation = cls.env["hr.leave.allocation"].create(
            {
                "name": f"{employee.name} annual allocation",
                "holiday_status_id": cls.annual_leave.id,
                "employee_id": employee.id,
                "number_of_days": 30,
                "state": "confirm",
                "date_from": date(2025, 1, 1),
                "date_to": date(2027, 12, 31),
            }
        )
        allocation.action_approve()
        return allocation

    @classmethod
    def _create_leave(
        cls, employee, leave_type, date_from, date_to, name, approve=True
    ):
        leave = (
            cls.env["hr.leave"]
            .with_context(leave_fast_create=True)
            .create(
                {
                    "name": name,
                    "employee_id": employee.id,
                    "holiday_status_id": leave_type.id,
                    "request_date_from": date_from,
                    "request_date_to": date_to,
                }
            )
        )
        if approve:
            leave.state = "validate"
        return leave

    def _wizard(self, year=2026, user=None, **values):
        wizard_model = self.env["l10n.pt.vacation.schedule.wizard"]
        if user is not None:
            wizard_model = wizard_model.with_user(user)
        return wizard_model.with_company(values.pop("company", self.company_a)).create(
            {"year": year, **values}
        )

    def _render_schedule(self, wizard, user=None, company=None):
        report = self.env["ir.actions.report"]
        if user is not None:
            report = report.with_user(user)
        report = report.with_company(company or self.company_a)
        html_content = report._render_qweb_html(
            "l10n_pt_hr_holidays.action_report_vacation_schedule", wizard.ids
        )[0]
        return html.fromstring(html_content)

    def _rows(self, table):
        return [
            [cell.text_content().strip() for cell in row.xpath("./td")]
            for row in table.xpath(".//tr[td]")
        ]

    def _expected_date(self, day):
        return format_date(self.env, day, lang_code="en_US")

    def test_prints_approved_vacations_in_company_schedule(self):
        """Approved annual leave prints in employee and date order."""
        wizard = self._wizard(user=self.manager)
        action = wizard.action_print()
        self.assertEqual(action["type"], "ir.actions.report")
        self.assertEqual(
            action["report_name"], "l10n_pt_hr_holidays.report_vacation_schedule"
        )

        doc = self._render_schedule(wizard, user=self.manager)
        page_text = doc.text_content()
        self.assertIn("Vacation Schedule", doc.xpath("string(//h2)"))
        self.assertIn("2026", doc.xpath("string(//h2)"))
        self.assertIn("Schedule Company A", page_text)

        self.assertEqual(
            self._rows(doc.xpath("//table[tbody/tr/td]")[0]),
            [
                [
                    "Alex Vacation",
                    self._expected_date(date(2025, 12, 29)),
                    self._expected_date(date(2026, 1, 2)),
                ],
                [
                    "Alex Vacation",
                    self._expected_date(date(2026, 6, 8)),
                    self._expected_date(date(2026, 6, 12)),
                ],
                [
                    "Unassigned Employee",
                    self._expected_date(date(2026, 9, 1)),
                    self._expected_date(date(2026, 9, 4)),
                ],
            ],
        )

        for forbidden in (
            "Pending Employee",
            "Absence Employee",
            "Other Company Employee",
            "Private vacation note",
            "Private sickness note",
        ):
            self.assertNotIn(forbidden, page_text)

    def test_shows_empty_year(self):
        """A year without approved leave shows an explicit empty message."""
        empty_doc = self._render_schedule(
            self._wizard(year=2030, user=self.manager), user=self.manager
        )
        self.assertIn(
            "No approved vacation periods for this selection.",
            empty_doc.text_content(),
        )
        self.assertFalse(empty_doc.xpath("//table[tbody/tr/td]"))

    def test_rejects_direct_report_access_and_other_company(self):
        """Only Time Off Administrators can print or render the schedule,
        and only for the current Portuguese company."""
        wizard = self._wizard(user=self.manager)

        with self.assertRaises(AccessError):
            wizard.with_user(self.plain_user).action_print()
        with self.assertRaises(AccessError):
            self._render_schedule(wizard, user=self.plain_user)

        foreign_wizard = self._wizard(user=self.manager, company_id=self.company_b.id)
        with self.assertRaises(ValidationError):
            foreign_wizard.action_print()
        with self.assertRaises(ValidationError):
            self._render_schedule(foreign_wizard, user=self.manager)

        us_wizard = self._wizard(user=self.manager, company=self.company_us)
        with self.assertRaises(ValidationError):
            us_wizard.action_print()
        with self.assertRaises(ValidationError):
            self._render_schedule(us_wizard, user=self.manager, company=self.company_us)
