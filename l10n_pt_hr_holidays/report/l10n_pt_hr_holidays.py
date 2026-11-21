# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models


class ReportVacationSchedule(models.AbstractModel):
    _name = "report.l10n_pt_hr_holidays.report_vacation_schedule"
    _description = "Portuguese Vacation Schedule Report"

    def _get_report_values(self, docids, data=None):
        wizard = self.env["l10n.pt.vacation.schedule.wizard"].browse(docids)
        wizard._check_report_selection()
        return {
            "doc_ids": wizard.ids,
            "doc_model": wizard._name,
            "docs": wizard,
            "schedule_leaves": wizard._get_schedule_leaves(),
        }
