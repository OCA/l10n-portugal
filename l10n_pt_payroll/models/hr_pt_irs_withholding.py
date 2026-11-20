# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class HrPtIrsWithholdingTable(models.Model):
    _name = "hr.pt.irs.withholding.table"
    _description = "IRS Withholding Table"
    _order = "date_start desc, region, table_id"

    name = fields.Char(compute="_compute_name")
    date_start = fields.Date(
        required=True,
        help="Start of the validity period approved by the Despacho.",
    )
    date_end = fields.Date(
        help="End of the validity period; empty means open-ended.",
    )
    region = fields.Selection(
        [
            ("continente", "Continente"),
            ("acores", "Açores"),
            ("madeira", "Madeira"),
        ],
        required=True,
    )
    table_id = fields.Many2one(
        "l10n.pt.irs.withholding.table",
        string="Table Variant",
        required=True,
        help="Official table number (I-XI) this set belongs to.",
    )
    ias = fields.Float(
        string="IAS",
        help="Index of social support for the period; used for the "
        "IRS Jovem exemption cap (55 x IAS per year).",
    )
    disabled_dep_parcela_single = fields.Float(
        string="Disabled Dependent Deduction - Single",
        help="Despacho n.5-a: amount added to the deduction for each "
        "dependent with a disability of 60% or more, for single "
        "workers and married workers filing alone.",
    )
    disabled_dep_parcela_joint = fields.Float(
        string="Disabled Dependent Deduction - Joint",
        help="Despacho n.5-a: amount added to the deduction for each "
        "dependent with a disability of 60% or more, for married "
        "workers filing jointly.",
    )
    spouse_disabled_parcela = fields.Float(
        string="Disabled Spouse Deduction",
        help="Despacho n.5-b: amount added to the deduction when a "
        "married worker filing alone has a spouse with a permanent "
        "disability of 60% or more and no category A/H income.",
    )
    pension_dep_parcela_single = fields.Float(
        string="Pension Dependent Deduction - Single",
        help="Despacho n.5-c: amount added to the deduction for each "
        "dependent of a pensioner who is single.",
    )
    pension_dep_parcela_joint = fields.Float(
        string="Pension Dependent Deduction - Joint",
        help="Despacho n.5-c: amount added to the deduction for each "
        "dependent of a married pensioner filing jointly.",
    )
    pension_dep_parcela_single_income = fields.Float(
        string="Pension Dependent Deduction - Single Income",
        help="Despacho n.5-c: amount added to the deduction for each "
        "dependent of a married pensioner filing alone.",
    )
    line_ids = fields.One2many(
        "hr.pt.irs.withholding.line",
        "table_id",
        string="Brackets",
    )

    # Unique per (period, region, variant); COALESCE makes the check
    # NULL-safe so open-ended sets (empty date_end) cannot duplicate.
    _date_region_table_uniq = models.UniqueIndex(
        "(date_start, region, table_id, COALESCE(date_end, '9999-12-31'::date))",
        "A withholding table set already exists for this period, "
        "region and table variant.",
    )

    @api.depends("table_id", "region", "date_start")
    def _compute_name(self):
        for table in self:
            table.name = (
                f"{table.table_id.code or ''} - "
                f"{dict(table._fields['region'].selection).get(table.region, '')}"
                f" - {table.date_start or ''}"
            )


class HrPtIrsWithholdingLine(models.Model):
    _name = "hr.pt.irs.withholding.line"
    _description = "IRS Withholding Bracket"
    _order = "table_id, lower_bound"

    table_id = fields.Many2one(
        "hr.pt.irs.withholding.table",
        required=True,
        ondelete="cascade",
        index=True,
    )
    lower_bound = fields.Float(
        required=True,
        help="Lower bound of the monthly taxable remuneration "
        "(exclusive): the bracket applies when lower_bound < R <= "
        "upper_bound.",
    )
    upper_bound = fields.Float(
        help="Upper bound of the bracket (inclusive). Leave empty or "
        "zero for the last, open-ended bracket.",
    )
    marginal_rate = fields.Float(
        string="Marginal Rate (%)",
        digits="Payroll Rate",
        required=True,
        help="Official maximum marginal rate for the bracket, e.g. 44.95.",
    )
    parcela_abater = fields.Char(
        required=True,
        default="0",
        help="Deduction expression evaluated with safe_eval and the "
        "variable R (monthly taxable remuneration). A plain number is "
        "a valid expression.",
    )
    dependent_parcela = fields.Float(
        string="Deduction per Dependent",
        help="Additional deduction for each IRS dependent.",
    )
    forces_disabled_parcela = fields.Float(
        string="Deduction - Armed Forces Disabled",
        help="Despacho n.5-d / formula 3.c: flat amount added to the "
        "deduction for pensioners with an armed forces disability "
        "(tables X and XI only).",
    )
    effective_rate_limit = fields.Float(
        string="Effective Rate at Limit (%)",
        help="Informational 'taxa efetiva no limite do escadao' "
        "published by the Despacho; never used in computation.",
    )
