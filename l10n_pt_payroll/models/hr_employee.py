# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # IRS withholding determinants are version fields; expose them on
    # the employee through delegation so the form edits the current
    # version.
    l10n_pt_irs_family_status = fields.Selection(
        related="version_id.l10n_pt_irs_family_status",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_dependents = fields.Integer(
        related="version_id.l10n_pt_irs_dependents",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_disabled_dependents = fields.Integer(
        related="version_id.l10n_pt_irs_disabled_dependents",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_disabled_dep_factor = fields.Integer(
        related="version_id.l10n_pt_irs_disabled_dep_factor",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_spouse_disabled = fields.Boolean(
        related="version_id.l10n_pt_irs_spouse_disabled",
        readonly=False,
        inherited=True,
    )
    l10n_pt_military_disabled = fields.Boolean(
        related="version_id.l10n_pt_military_disabled",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_region = fields.Selection(
        related="version_id.l10n_pt_irs_region",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_pensioner = fields.Boolean(
        related="version_id.l10n_pt_irs_pensioner",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_non_resident = fields.Boolean(
        related="version_id.l10n_pt_irs_non_resident",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_preferred_rate = fields.Float(
        related="version_id.l10n_pt_irs_preferred_rate",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_jovem = fields.Boolean(
        related="version_id.l10n_pt_irs_jovem",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_income_years = fields.Integer(
        related="version_id.l10n_pt_irs_income_years",
        readonly=False,
        inherited=True,
    )
    l10n_pt_irs_table_id = fields.Many2one(
        related="version_id.l10n_pt_irs_table_id",
        inherited=True,
    )
