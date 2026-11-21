# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user
from odoo.tests.common import TransactionCase


class TestGeneratePublicHolidays(TransactionCase):
    """Feature coverage for the Portuguese public holiday generator."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pt = cls.env.ref("base.pt")
        cls.manager = new_test_user(
            cls.env,
            login="pt_public_holidays_manager",
            groups="hr_holidays.group_hr_holidays_manager",
            lang="en_US",
            tz="America/New_York",
        )
        cls.ordinary = new_test_user(
            cls.env,
            login="pt_public_holidays_employee",
            groups="base.group_user",
            lang="en_US",
        )
        cls.Wizard = cls.env["l10n.pt.generate.public.holidays"].with_user(cls.manager)
        cls.Catalog = cls.env["calendar.public.holiday"].with_user(cls.manager)
        cls.Line = cls.env["calendar.public.holiday.line"].with_user(cls.manager)

    def _wizard(self, year, **kwargs):
        return self.Wizard.create({"year": year, **kwargs})

    def _portuguese_catalog(self, year):
        return self.Catalog.search(
            [("year", "=", year), ("country_id", "=", self.pt.id)]
        )

    def test_national_holidays_are_applied_once(self):
        """A Time Off Administrator generates each mandatory date once."""
        spain = self.env.ref("base.es")
        es_catalog = self.Catalog.create({"country_id": spain.id, "year": 2026})
        self.Line.create(
            {
                "public_holiday_id": es_catalog.id,
                "date": date(2026, 1, 6),
                "name": "Three Kings Day",
            }
        )

        wizard = self._wizard(2026)
        self.assertEqual(wizard.preview.count("To add"), 13)
        self.assertFalse(self._portuguese_catalog(2026))

        wizard.action_apply()

        catalogs = self._portuguese_catalog(2026)
        self.assertEqual(len(catalogs), 1)
        lines = catalogs.line_ids
        self.assertEqual(len(lines), 13)
        dates = set(lines.mapped("date"))
        self.assertIn(date(2026, 4, 3), dates)  # Good Friday
        self.assertIn(date(2026, 4, 5), dates)  # Easter Sunday
        self.assertIn(date(2026, 6, 4), dates)  # Corpus Christi
        self.assertIn(date(2026, 12, 25), dates)  # Christmas Day
        self.assertNotIn(date(2026, 2, 17), dates)  # Carnival stays optional
        self.assertTrue(all(not line.state_ids for line in lines))

        line_ids = set(lines.ids)
        result = wizard.action_apply()
        self.assertIn("Added: 0", result["params"]["message"])
        self.Catalog.invalidate_model()
        self.assertEqual(set(self._portuguese_catalog(2026).line_ids.ids), line_ids)
        self.assertEqual(
            self.Line.search_count([("public_holiday_id", "=", es_catalog.id)]),
            1,
        )

    def test_carry_forward_recalculates_optional_holidays_and_skips_one_offs(
        self,
    ):
        """Linked optional rules carry forward by rule, not copied dates."""
        carnival = self.env.ref(
            "l10n_pt_hr_holidays_public.public_holiday_rule_carnival"
        )
        wizard = self._wizard(2026, optional_rule_ids=[Command.set(carnival.ids)])
        wizard.action_apply()
        catalog_2026 = self._portuguese_catalog(2026)
        carnival_line = catalog_2026.line_ids.filtered(
            lambda line: line.name == "Carnival Tuesday"
        )
        self.assertEqual(len(carnival_line), 1)
        self.assertEqual(carnival_line.date, date(2026, 2, 17))

        self.Line.create(
            {
                "public_holiday_id": catalog_2026.id,
                "date": date(2026, 6, 15),
                "name": "One-off closure",
            }
        )

        plain_2027 = self._wizard(2027)
        self.assertNotIn("Carnival Tuesday", plain_2027.preview)

        carried = self._wizard(2027, use_previous_year=True)
        self.assertEqual(carried.preview.count("Carnival Tuesday"), 1)
        self.assertNotIn("One-off closure", carried.preview)
        carried.action_apply()

        catalog_2027 = self._portuguese_catalog(2027)
        carried_line = catalog_2027.line_ids.filtered(
            lambda line: line.name == "Carnival Tuesday"
        )
        self.assertEqual(len(carried_line), 1)
        self.assertEqual(carried_line.date, date(2027, 2, 9))
        self.assertFalse(
            catalog_2027.line_ids.filtered(lambda line: line.name == "One-off closure")
        )
        self.assertTrue(carnival_line.exists())
        self.assertEqual(self.Line.search_count([("name", "=", "One-off closure")]), 1)

    def test_manual_lines_are_preserved(self):
        """Manual nationwide and regional entries stay untouched."""
        state = self.env["res.country.state"].create(
            {
                "name": "Test Portuguese Region",
                "code": "PXTEST",
                "country_id": self.pt.id,
            }
        )
        catalog = self.Catalog.create({"country_id": self.pt.id, "year": 2026})
        nationwide = self.Line.create(
            {
                "public_holiday_id": catalog.id,
                "date": date(2026, 1, 1),
                "name": "Existing nationwide",
            }
        )
        regional = self.Line.create(
            {
                "public_holiday_id": catalog.id,
                "date": date(2026, 6, 10),
                "name": "Existing regional",
                "state_ids": [Command.set(state.ids)],
            }
        )

        wizard = self._wizard(2026)
        self.assertEqual(wizard.preview.count("Already covered"), 1)
        self.assertEqual(wizard.preview.count("Regional overlap: review manually"), 1)
        self.assertEqual(wizard.preview.count("To add"), 11)

        result = wizard.action_apply()
        self.assertIn("Added: 11", result["params"]["message"])
        self.assertIn("Already covered: 1", result["params"]["message"])
        self.assertIn("Regional overlaps: 1", result["params"]["message"])

        self.Line.invalidate_model()
        self.assertEqual(nationwide.name, "Existing nationwide")
        self.assertEqual(nationwide.date, date(2026, 1, 1))
        self.assertFalse(nationwide.state_ids)
        self.assertEqual(regional.name, "Existing regional")
        self.assertEqual(regional.date, date(2026, 6, 10))
        self.assertEqual(regional.state_ids, state)

        self.Catalog.invalidate_model()
        lines = catalog.line_ids
        self.assertEqual(len(lines), 13)
        self.assertEqual(
            lines.filtered(lambda line: line.date == date(2026, 1, 1)).mapped("name"),
            ["Existing nationwide"],
        )
        self.assertEqual(
            lines.filtered(lambda line: line.date == date(2026, 6, 10)).mapped("name"),
            ["Existing regional"],
        )

    def test_colliding_holidays_share_one_line(self):
        """Easter Sunday and Freedom Day share 25 April 2038."""
        wizard = self._wizard(2038)
        preview_lines = wizard.preview.splitlines()
        self.assertEqual(len(preview_lines), 12)
        combined = [line for line in preview_lines if "Freedom Day" in line]
        self.assertEqual(len(combined), 1)
        self.assertIn("Easter Sunday", combined[0])

        wizard.action_apply()
        catalog = self._portuguese_catalog(2038)
        self.assertEqual(len(catalog.line_ids), 12)
        shared = catalog.line_ids.filtered(lambda line: line.date == date(2038, 4, 25))
        self.assertEqual(len(shared), 1)
        self.assertIn("Freedom Day", shared.name)
        self.assertIn("Easter Sunday", shared.name)

        result = wizard.action_apply()
        self.assertIn("Added: 0", result["params"]["message"])
        self.Catalog.invalidate_model()
        self.assertEqual(len(self._portuguese_catalog(2038).line_ids), 12)

    def test_regional_context_defaults_do_not_scope_generated_holidays(self):
        """The generator remains nationwide when opened with a regional default."""
        state = self.env["res.country.state"].create(
            {
                "name": "Test Default Region",
                "code": "PXDEFAULT",
                "country_id": self.pt.id,
            }
        )
        wizard = self._wizard(2026).with_context(
            default_state_ids=[Command.set(state.ids)]
        )
        wizard.action_apply()
        lines = self._portuguese_catalog(2026).line_ids
        self.assertEqual(len(lines), 13)
        self.assertFalse(lines.mapped("state_ids"))

    def test_non_manager_cannot_generate(self):
        """Only Time Off Administrators can generate holidays or rules."""
        with self.assertRaises(AccessError):
            self.env["l10n.pt.generate.public.holidays"].with_user(
                self.ordinary
            ).create({"year": 2026})

        wizard = self._wizard(2026)
        with self.assertRaises(AccessError):
            wizard.with_user(self.ordinary).action_apply()
        self.assertFalse(self._portuguese_catalog(2026))

        with self.assertRaises(AccessError):
            self.env["l10n.pt.public.holiday.rule"].with_user(self.ordinary).create(
                {"name": "Sneaky holiday", "rule_type": "fixed"}
            )

        with self.assertRaises(ValidationError):
            self._wizard(2016).action_apply()
