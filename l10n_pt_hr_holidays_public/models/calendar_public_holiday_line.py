# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CalendarPublicHolidayLine(models.Model):
    _inherit = "calendar.public.holiday.line"

    l10n_pt_holiday_rule_ids = fields.Many2many(
        "l10n.pt.public.holiday.rule",
        "l10n_pt_line_holiday_rule_rel",
        string="Portuguese Holiday Rules",
        copy=False,
        groups="hr_holidays.group_hr_holidays_manager",
        help="Unlinked holidays are one-offs and are not carried forward "
        "by the Portuguese wizard.",
    )
