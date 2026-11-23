# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import timedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestHourlyRemuneration(TransactionCase):
    """Statutory hourly remuneration: monthly * 12 / (52 * weekly PNT)
    on the contract version effective for the work."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create({"name": "Hourly Test"})
        cls.version = cls.employee.version_id

    def test_hourly_rate_uses_contract_pnt(self):
        self.version.l10n_pt_weekly_pnt_hours = 20.0
        rate = self.version._l10n_pt_hourly_remuneration(1000.0)
        self.assertAlmostEqual(rate, 11.538461538461538)

    def test_hourly_rate_uses_version_effective_on_date(self):
        """Each dated contract version keeps its own PNT: the historical
        40-hour version yields half the rate of the newer 20-hour one."""
        self.version.l10n_pt_weekly_pnt_hours = 40.0
        effective_date = self.version.date_version + timedelta(days=1)
        self.employee.create_version(
            {
                "date_version": effective_date,
                "l10n_pt_weekly_pnt_hours": 20.0,
            }
        )
        older = self.employee._get_version(self.version.date_version)
        newer = self.employee._get_version(effective_date)
        self.assertNotEqual(older, newer)
        self.assertAlmostEqual(
            older._l10n_pt_hourly_remuneration(1000.0), 5.769230769230769
        )
        self.assertAlmostEqual(
            newer._l10n_pt_hourly_remuneration(1000.0), 11.538461538461538
        )

    def test_hourly_rate_requires_pnt(self):
        self.version.l10n_pt_weekly_pnt_hours = 0.0
        with self.assertRaises(UserError):
            self.version._l10n_pt_hourly_remuneration(1000.0)
