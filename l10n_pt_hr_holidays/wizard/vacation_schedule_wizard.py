# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import date

from odoo import fields, models
from odoo.exceptions import AccessError, ValidationError


class VacationScheduleWizard(models.TransientModel):
    _name = "l10n.pt.vacation.schedule.wizard"
    _description = "Portuguese Vacation Schedule"

    year = fields.Integer(
        required=True,
        default=lambda self: fields.Date.context_today(self).year,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
    )

    def action_print(self):
        self._check_report_selection()
        return self.env.ref(
            "l10n_pt_hr_holidays.action_report_vacation_schedule"
        ).report_action(self)

    def _check_report_selection(self):
        self.ensure_one()
        if not self.env.user.has_group("hr_holidays.group_hr_holidays_manager"):
            raise AccessError(
                self.env._(
                    "Only Time Off Administrators can print the vacation schedule."
                )
            )
        self.check_access("read")
        if (
            self.company_id != self.env.company
            or self.company_id.country_id.code != "PT"
        ):
            raise ValidationError(
                self.env._(
                    "Select the current Portuguese company to print the "
                    "vacation schedule."
                )
            )
        if not 1 <= self.year <= 9999:
            raise ValidationError(self.env._("Enter a year between 1 and 9999."))

    def _get_schedule_leaves(self):
        self.ensure_one()
        start, end = date(self.year, 1, 1), date(self.year, 12, 31)
        annual_leave = self.env.ref("l10n_pt_hr_holidays.leave_type_annual_leave")
        leaves = self.env["hr.leave"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("employee_company_id", "=", self.company_id.id),
                ("state", "=", "validate"),
                ("holiday_status_id", "=", annual_leave.id),
                ("request_date_from", "<=", end),
                ("request_date_to", ">=", start),
            ]
        )
        return leaves.sorted(
            key=lambda leave: (
                leave.employee_id.name.casefold(),
                leave.request_date_from,
                leave.request_date_to,
                leave.id,
            )
        )
