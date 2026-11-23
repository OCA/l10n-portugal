# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # Version fields are exposed on the employee through delegation:
    # each field is re-declared as related to version_id so that reads
    # and writes go to the employee's current version.
    l10n_pt_id_doc_type = fields.Selection(
        related="version_id.l10n_pt_id_doc_type",
        readonly=False,
        inherited=True,
        groups="hr.group_hr_user",
    )
    l10n_pt_id_doc_expiry = fields.Date(
        related="version_id.l10n_pt_id_doc_expiry",
        readonly=False,
        inherited=True,
        groups="hr.group_hr_user",
    )
    l10n_pt_irct_id = fields.Many2one(
        related="version_id.l10n_pt_irct_id",
        readonly=False,
        inherited=True,
    )
    l10n_pt_professional_category_id = fields.Many2one(
        related="version_id.l10n_pt_professional_category_id",
        readonly=False,
        inherited=True,
    )
    l10n_pt_union_id = fields.Many2one(
        related="version_id.l10n_pt_union_id",
        readonly=False,
        inherited=True,
    )
    l10n_pt_profession_id = fields.Many2one(
        related="version_id.l10n_pt_profession_id",
        readonly=False,
        inherited=True,
    )
    l10n_pt_pay_grade_id = fields.Many2one(
        related="version_id.l10n_pt_pay_grade_id",
        readonly=False,
        inherited=True,
    )
    l10n_pt_ss_regime_id = fields.Many2one(
        related="version_id.l10n_pt_ss_regime_id",
        readonly=False,
        inherited=True,
    )
    l10n_pt_disability_degree = fields.Integer(
        related="version_id.l10n_pt_disability_degree",
        readonly=False,
        inherited=True,
    )
    l10n_pt_qualification_level = fields.Selection(
        related="version_id.l10n_pt_qualification_level",
        readonly=False,
        inherited=True,
    )
    l10n_pt_work_insurance_id = fields.Many2one(
        related="version_id.l10n_pt_work_insurance_id",
        readonly=False,
        inherited=True,
    )
    l10n_pt_work_time_arrangement_id = fields.Many2one(
        related="version_id.l10n_pt_work_time_arrangement_id",
        readonly=False,
        inherited=True,
    )
    l10n_pt_weekly_pnt_hours = fields.Float(
        related="version_id.l10n_pt_weekly_pnt_hours",
        readonly=False,
        inherited=True,
    )
    l10n_pt_full_time_reference_hours = fields.Float(
        related="version_id.l10n_pt_full_time_reference_hours",
        readonly=False,
        inherited=True,
    )
    l10n_pt_part_time = fields.Boolean(
        related="version_id.l10n_pt_part_time",
        inherited=True,
    )
    l10n_pt_establishment_id = fields.Many2one(
        related="version_id.l10n_pt_establishment_id",
        inherited=True,
        readonly=False,
        groups="hr.group_hr_user",
    )

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(
            [self._prepare_l10n_pt_establishment_values(vals) for vals in vals_list]
        )

    def _prepare_l10n_pt_establishment_values(self, vals):
        if (
            "l10n_pt_establishment_id" in vals
            or "default_l10n_pt_establishment_id" in self.env.context
            or vals.get("version_id")
        ):
            return vals
        company = self.env["res.company"].browse(
            vals.get("company_id")
            or self.env.context.get("default_company_id")
            or self.env.company.id
        )
        if (
            company.country_id.code == "PT"
            and (establishment := company.l10n_pt_default_establishment_id).active
        ):
            return dict(vals, l10n_pt_establishment_id=establishment.id)
        return vals

    def write(self, vals):
        if "company_id" in vals:
            self.check_access("write")
            # sudo is used only to detect the existence of assignments on
            # archived or otherwise hidden versions; it never returns
            # records and write access was checked above.
            if (
                self.env["hr.version"]
                .sudo()
                .with_context(active_test=False)
                .search_count(
                    [
                        ("employee_id", "in", self.ids),
                        ("l10n_pt_establishment_id", "!=", False),
                        (
                            "l10n_pt_establishment_id.company_id",
                            "!=",
                            vals["company_id"],
                        ),
                    ],
                    limit=1,
                )
            ):
                raise ValidationError(
                    self.env._(
                        "Create a separate employee record when moving an "
                        "employee with an establishment assignment to a "
                        "different company."
                    )
                )
        return super().write(vals)
