# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


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
