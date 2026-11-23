# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import math

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

# Non-residents are withheld at a flat 25% on Portuguese-source
# employment and pension income, without table deductions.
NON_RESIDENT_RATE = 25.0


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

    @api.model
    def _get_effective_table(self, payment_date, region, table_variant):
        # Overlapping sets are possible when a Despacho corrects part of
        # a period: the most recently effective set wins, and for equal
        # start dates the narrower (earlier-ending) window is preferred.
        table = self.search(
            [
                ("date_start", "<=", payment_date),
                "|",
                ("date_end", "=", False),
                ("date_end", ">=", payment_date),
                ("region", "=", region),
                ("table_id", "=", table_variant.id),
            ],
            order="date_start desc, date_end asc, id desc",
            limit=1,
        )
        if not table:
            raise UserError(
                self.env._(
                    "No IRS withholding table covers %(date)s for region "
                    "%(region)s and table %(variant)s. Import the tables "
                    "for the period.",
                    date=payment_date,
                    region=region,
                    variant=table_variant.code,
                )
            )
        return table

    def _get_bracket(self, taxable):
        self.ensure_one()
        bracket = self.line_ids.filtered(
            lambda line: line.lower_bound < taxable <= (line.upper_bound or math.inf)
        )
        if len(bracket) != 1:
            raise UserError(
                self.env._(
                    "No unique IRS withholding bracket found for "
                    "remuneration %(amount)s on table %(table)s.",
                    amount=taxable,
                    table=self.display_name,
                )
            )
        return bracket[0]

    def _disabled_dep_parcela(self, version):
        # Despacho n.5-a: single workers and married workers filing
        # alone get the higher amount; joint filers get half of it.
        self.ensure_one()
        if version.l10n_pt_irs_family_status == "married_joint":
            return self.disabled_dep_parcela_joint
        return self.disabled_dep_parcela_single

    def _pension_dep_parcela(self, version):
        # Despacho n.5-c for pension tables VIII-XI.
        self.ensure_one()
        status = version.l10n_pt_irs_family_status
        if status == "married_single_income":
            return self.pension_dep_parcela_single_income
        if status == "married_joint":
            return self.pension_dep_parcela_joint
        return self.pension_dep_parcela_single

    # IRS Jovem (art. 12-B CIRS): the exemption applies to income up to
    # 55 x IAS per year; payroll withholds on the non-exempt portion.
    # Despacho n.5-g caps the accumulated monthly exemptions at the
    # annual limit divided by 14, approximated here as a monthly cap.
    def _irs_jovem_base(self, taxable, version):
        # income_years counts the years of income already obtained, so
        # the current year is income_years + 1.
        income_year = (version.l10n_pt_irs_income_years or 0) + 1
        if income_year <= 1:
            exemption = 1.0
        elif income_year <= 4:
            exemption = 0.75
        elif income_year <= 7:
            exemption = 0.50
        elif income_year <= 10:
            exemption = 0.25
        else:
            exemption = 0.0
        monthly_cap = 55.0 * (self.ias or 0.0) / 14.0
        exempt = min(taxable * exemption, monthly_cap)
        return taxable - exempt

    # Monthly IRS retention (retencao na fonte) per the annual Despacho
    # tables. Returns the positive retention amount, truncated down to
    # the euro as the Despacho requires, plus the taxable base, applied
    # rate and formula deductions for payslip line presentation.
    @api.model
    def _calculate_withholding(
        self, version, payment_date, taxable, *, allowance=0.0, previous_allowance=0.0
    ):
        if (allowance or previous_allowance) and (
            not version.l10n_pt_irs_non_resident
            or version.l10n_pt_irs_pensioner
            or not version.l10n_pt_irs_single_payer_declared
        ):
            raise UserError(
                self.env._(
                    "The single-payer allowance requires a non-resident worker "
                    "with a written single-payer declaration."
                )
            )
        if taxable <= 0:
            return dict(amount=0.0, taxable=taxable, base=0.0, rate=None, parcela=0.0)
        if version.l10n_pt_irs_non_resident:
            base = max(taxable - allowance - previous_allowance, 0.0)
            return dict(
                amount=float(math.floor(base * NON_RESIDENT_RATE / 100.0)),
                taxable=taxable,
                base=base,
                rate=NON_RESIDENT_RATE if base else None,
                parcela=0.0,
                allowance_applied=allowance,
            )
        table_variant = version.l10n_pt_irs_table_id
        if not table_variant:
            raise UserError(
                self.env._(
                    "Employee %(employee)s has no IRS withholding table "
                    "variant: set the IRS family status on the contract.",
                    employee=version.employee_id.name,
                )
            )
        table = self._get_effective_table(
            payment_date, version.l10n_pt_irs_region or "continente", table_variant
        )
        base = taxable
        if version.l10n_pt_irs_jovem and not version.l10n_pt_irs_pensioner:
            base = table._irs_jovem_base(taxable, version)
        if base <= 0:
            return dict(amount=0.0, taxable=taxable, base=base, rate=None, parcela=0.0)
        bracket = table._get_bracket(taxable)
        # Despacho n.5-h: three or more dependents reduce the marginal
        # rate by 1 p.p. A preferred rate (n.5-e) replaces the marginal
        # rate but keeps every deduction unchanged.
        rate = bracket.marginal_rate - (
            1.0 if (version.l10n_pt_irs_dependents or 0) >= 3 else 0.0
        )
        if version.l10n_pt_irs_preferred_rate:
            rate = version.l10n_pt_irs_preferred_rate
        dependents = version.l10n_pt_irs_dependents or 0
        disabled_dependents = version.l10n_pt_irs_disabled_dependents or 0
        parcela = safe_eval(bracket.parcela_abater or "0", {"R": taxable})
        parcela += bracket.dependent_parcela * dependents
        # Despacho n.5-a + n.6: each dependent with a disability of 60%
        # or more adds the per-period amount by family situation,
        # optionally multiplied by the factor the employee declared.
        if disabled_dependents:
            parcela += (
                table._disabled_dep_parcela(version)
                * disabled_dependents
                * (version.l10n_pt_irs_disabled_dep_factor or 1)
            )
        # Despacho n.5-b: married worker filing alone whose spouse has a
        # disability of 60% or more and no category A/H income.
        if (
            version.l10n_pt_irs_family_status == "married_single_income"
            and version.l10n_pt_irs_spouse_disabled
        ):
            parcela += table.spouse_disabled_parcela
        if version.l10n_pt_irs_pensioner:
            # Despacho n.5-c: pensioners with dependents get an extra
            # per-dependent amount that depends on the family situation.
            parcela += table._pension_dep_parcela(version) * dependents
            # Despacho n.5-d / formula 3.c: armed forces disability adds
            # a flat amount on tables X and XI.
            if version.l10n_pt_military_disabled:
                parcela += bracket.forces_disabled_parcela
        retention = max(taxable * rate / 100.0 - parcela, 0.0)
        if base < taxable:
            # AT Circular 20274/2025: apply the full-income effective
            # rate to the non-exempt portion, not a second table bracket.
            rate = retention / taxable * 100.0
            retention = retention * base / taxable
            parcela = 0.0
        return dict(
            amount=float(math.floor(retention)),
            taxable=taxable,
            base=base,
            rate=rate,
            parcela=parcela,
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
