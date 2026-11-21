# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from dateutil.easter import easter

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import format_date


class L10nPtGeneratePublicHolidays(models.TransientModel):
    _name = "l10n.pt.generate.public.holidays"
    _description = "Generate Portuguese Public Holidays"

    year = fields.Integer(
        required=True,
        default=lambda self: fields.Date.context_today(self).year,
    )
    use_previous_year = fields.Boolean(
        string="Use Last Year's Optional Rules",
        help="Carry linked optional rules forward, but not one-off holidays.",
    )
    optional_rule_ids = fields.Many2many(
        "l10n.pt.public.holiday.rule",
        "l10n_pt_gen_holiday_rule_rel",
        string="Additional Optional Rules",
        domain="[('active', '=', True), ('mandatory', '=', False)]",
    )
    preview = fields.Text(compute="_compute_preview")

    @api.depends(
        "year",
        "use_previous_year",
        "optional_rule_ids",
        "optional_rule_ids.active",
        "optional_rule_ids.mandatory",
        "optional_rule_ids.name",
        "optional_rule_ids.rule_type",
        "optional_rule_ids.month",
        "optional_rule_ids.day",
        "optional_rule_ids.easter_offset",
    )
    @api.depends_context("lang", "uid")
    def _compute_preview(self):
        labels = {
            "add": self.env._("To add"),
            "covered": self.env._("Already covered"),
            "regional": self.env._("Regional overlap: review manually"),
        }
        for wizard in self:
            wizard.preview = False
            if not wizard._valid_selection():
                continue
            _target, plan = wizard._holiday_plan()
            wizard.preview = "\n".join(
                self.env._(
                    "%(date)s | %(holiday)s | %(status)s",
                    date=format_date(self.env, day),
                    holiday=name,
                    status=labels[status],
                )
                for day, name, _rules, status in plan
            )

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("hr_holidays.group_hr_holidays_manager"):
            raise AccessError(
                self.env._("Only Time Off Administrators can generate public holidays.")
            )
        self.check_access("read")
        self.optional_rule_ids.check_access("read")
        if not self._valid_selection():
            raise ValidationError(
                self.env._(
                    "Choose a year from 2017 to 2099 and only active optional rules."
                )
            )
        target, plan = self._holiday_plan()
        additions = [
            (day, name, rules) for day, name, rules, status in plan if status == "add"
        ]
        covered = sum(status == "covered" for _d, _n, _r, status in plan)
        regional = sum(status == "regional" for _d, _n, _r, status in plan)
        if additions:
            if not target:
                target = self.env["calendar.public.holiday"].create(
                    {
                        "country_id": self.env.ref("base.pt").id,
                        "year": self.year,
                    }
                )
            self.env["calendar.public.holiday.line"].create(
                [
                    self._prepare_holiday_line_values(target, day, name, rules)
                    for day, name, rules in additions
                ]
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Portuguese Public Holidays"),
                "message": self.env._(
                    "Added: %(added)s. Already covered: %(covered)s. "
                    "Regional overlaps: %(regional)s.",
                    added=len(additions),
                    covered=covered,
                    regional=regional,
                ),
                "type": "warning" if regional else "success",
                "sticky": bool(regional),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _valid_selection(self):
        return 2017 <= self.year <= 2099 and all(
            rule.active and not rule.mandatory for rule in self.optional_rule_ids
        )

    def _holiday_plan(self):
        pt = self.env.ref("base.pt")
        catalogs = self.env["calendar.public.holiday"].search(
            [
                ("year", "=", self.year),
                ("country_id", "in", [False, pt.id]),
            ]
        )
        target = catalogs.filtered(lambda catalog: catalog.country_id == pt)[:1]
        existing = catalogs.line_ids.grouped("date")
        plan = []
        for day, rules in self._rules_by_date(pt).items():
            name = " / ".join(rules.mapped("name"))
            same_day = existing.get(day, self.env["calendar.public.holiday.line"])
            if any(not line.state_ids for line in same_day):
                status = "covered"
            elif any(line.state_ids.country_id & pt for line in same_day):
                status = "regional"
            else:
                status = "add"
            plan.append((day, name, rules, status))
        return target, plan

    def _rules_by_date(self, pt):
        rules_model = self.env["l10n.pt.public.holiday.rule"]
        mandatory = rules_model.search(
            [("active", "=", True), ("mandatory", "=", True)]
        )
        selected = mandatory | self.optional_rule_ids
        if self.use_previous_year:
            previous = self.env["calendar.public.holiday"].search(
                [
                    ("year", "=", self.year - 1),
                    ("country_id", "=", pt.id),
                ]
            )
            previous_rules = previous.line_ids.filtered(
                lambda line: not line.state_ids
            ).l10n_pt_holiday_rule_ids
            selected |= previous_rules.filtered(
                lambda rule: rule.active and not rule.mandatory
            )
        easter_day = easter(self.year)
        by_date = {}
        for rule in selected.sorted():
            if day := rule._date_in_year(self.year, easter_day):
                by_date[day] = by_date.get(day, rules_model) | rule
        return dict(sorted(by_date.items()))

    def _prepare_holiday_line_values(self, target, day, name, rules):
        return {
            "public_holiday_id": target.id,
            "date": day,
            "name": name,
            "state_ids": [Command.clear()],
            "meeting_id": False,
            "variable_date": any(rule.rule_type == "easter" for rule in rules),
            "l10n_pt_holiday_rule_ids": [Command.set(rules.ids)],
        }
