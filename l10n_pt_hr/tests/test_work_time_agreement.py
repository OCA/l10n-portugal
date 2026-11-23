# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestWorkTimeAgreement(TransactionCase):
    """Contract work time agreement: the full-time reference snapshots
    from the collective contract or the employee's own company default,
    and part-time is derived from PNT vs reference."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create(
            {
                "name": "PT Agreement Company B",
                "country_id": cls.env.ref("base.pt").id,
                "l10n_pt_full_time_hours": 40.0,
            }
        )
        cls.irct_35 = cls.env["l10n.pt.collective.contract"].create(
            {"name": "CCT 35h", "l10n_pt_full_time_hours": 35.0}
        )
        cls.employees = cls.env["hr.employee"].with_context(
            allowed_company_ids=[cls.company_a.id, cls.company_b.id]
        )

    def _create_pt_employee(self, **values):
        vals = {"name": "PT Agreement Employee", "company_id": self.company_b.id}
        vals.update(values)
        return self.employees.create(vals)

    def test_reference_from_collective_contract(self):
        """PNT equal to the collective reference is not part-time, even
        though the company default is higher."""
        employee = self._create_pt_employee(
            l10n_pt_irct_id=self.irct_35.id, l10n_pt_weekly_pnt_hours=35.0
        )
        version = employee.version_id
        self.assertEqual(version.l10n_pt_full_time_reference_hours, 35.0)
        self.assertFalse(version.l10n_pt_part_time)

    def test_reference_falls_back_to_employee_company(self):
        """Without a collective reference, the version's own company
        default applies — not the active company's."""
        self.company_a.l10n_pt_full_time_hours = 38.0
        employee = self._create_pt_employee(l10n_pt_weekly_pnt_hours=35.0)
        version = employee.version_id
        self.assertEqual(version.company_id, self.company_b)
        self.assertEqual(version.l10n_pt_full_time_reference_hours, 40.0)
        self.assertTrue(version.l10n_pt_part_time)

    def test_explicit_reference_override_wins(self):
        """An explicit reference is never rewritten by the snapshot,
        even when determinants change afterwards."""
        employee = self._create_pt_employee(
            l10n_pt_irct_id=self.irct_35.id, l10n_pt_weekly_pnt_hours=35.0
        )
        version = employee.version_id
        version.l10n_pt_full_time_reference_hours = 36.0
        self.irct_35.l10n_pt_full_time_hours = 37.0
        version.write({"l10n_pt_weekly_pnt_hours": 35.0})
        self.assertEqual(version.l10n_pt_full_time_reference_hours, 36.0)
        self.assertTrue(version.l10n_pt_part_time)

    def test_default_and_calendar_edits_keep_saved_reference(self):
        """Editing company/collective defaults or the shared working-time
        calendar never rewrites references already saved on contract
        versions."""
        calendar = self.company_b.resource_calendar_id
        employee_irct = self._create_pt_employee(
            resource_calendar_id=calendar.id,
            l10n_pt_irct_id=self.irct_35.id,
            l10n_pt_weekly_pnt_hours=35.0,
        )
        employee_plain = self._create_pt_employee(
            name="PT Agreement Employee plain",
            resource_calendar_id=calendar.id,
            l10n_pt_weekly_pnt_hours=35.0,
        )
        version_irct = employee_irct.version_id
        version_plain = employee_plain.version_id
        self.assertEqual(version_irct.l10n_pt_full_time_reference_hours, 35.0)
        self.assertEqual(version_plain.l10n_pt_full_time_reference_hours, 40.0)

        self.company_b.l10n_pt_full_time_hours = 37.0
        self.irct_35.l10n_pt_full_time_hours = 38.0
        calendar.write({"schedule_type": "flexible", "hours_per_week": 30.0})
        self.assertEqual(calendar.hours_per_week, 30.0)

        self.assertEqual(version_irct.l10n_pt_full_time_reference_hours, 35.0)
        self.assertEqual(version_plain.l10n_pt_full_time_reference_hours, 40.0)
        self.assertEqual(version_irct.l10n_pt_weekly_pnt_hours, 35.0)
        self.assertEqual(version_plain.l10n_pt_weekly_pnt_hours, 35.0)

    def test_snapshot_on_later_pnt_entry(self):
        """A version created without hours gets the reference when the
        PNT is entered afterwards."""
        employee = self._create_pt_employee(l10n_pt_irct_id=self.irct_35.id)
        version = employee.version_id
        self.assertFalse(version.l10n_pt_full_time_reference_hours)
        self.assertFalse(version.l10n_pt_part_time)
        version.write({"l10n_pt_weekly_pnt_hours": 35.0})
        self.assertEqual(version.l10n_pt_full_time_reference_hours, 35.0)
        self.assertFalse(version.l10n_pt_part_time)

    def test_above_reference_is_not_part_time(self):
        employee = self._create_pt_employee(
            l10n_pt_irct_id=self.irct_35.id, l10n_pt_weekly_pnt_hours=40.0
        )
        version = employee.version_id
        self.assertEqual(version.l10n_pt_full_time_reference_hours, 35.0)
        self.assertFalse(version.l10n_pt_part_time)

    def test_negative_hours_rejected(self):
        employee = self._create_pt_employee()
        with self.assertRaises(ValidationError):
            employee.version_id.write({"l10n_pt_weekly_pnt_hours": -1})
