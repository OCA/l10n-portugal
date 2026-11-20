# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import math

from odoo import models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

# Non-residents are withheld at a flat 25% on Portuguese-source
# employment and pension income, without table deductions.
NON_RESIDENT_RATE = 25.0


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    # Monthly IRS retention (retencao na fonte) per the annual Despacho
    # tables. Called from the IRS salary rule's python compute with the
    # payslip's result_rules; returns the positive retention amount,
    # truncated down to the euro as the Despacho requires.
    def _l10n_pt_irs_retention(self, result_rules):
        self.ensure_one()
        version = self.contract_id
        if not version:
            raise UserError(self.env._("The payslip has no contract."))
        structure = self.struct_id or version.struct_id
        taxable = 0.0
        for rule in structure.get_all_rules():
            if (
                rule.l10n_pt_irs_taxable
                and rule.code
                and rule.code in result_rules.dict
            ):
                taxable += result_rules.dict[rule.code].total * rule.l10n_pt_irs_taxable
        if taxable <= 0:
            return 0.0
        if version.l10n_pt_irs_non_resident:
            return float(math.floor(taxable * NON_RESIDENT_RATE / 100.0))
        table = self._l10n_pt_irs_withholding_table(version)
        base = taxable
        if version.l10n_pt_irs_jovem and not version.l10n_pt_irs_pensioner:
            base = self._l10n_pt_irs_jovem_base(taxable, table)
        if base <= 0:
            return 0.0
        bracket = table.line_ids.filtered(
            lambda line: line.lower_bound < base <= (line.upper_bound or math.inf)
        )
        if len(bracket) != 1:
            raise UserError(
                self.env._(
                    "No unique IRS withholding bracket found for "
                    "remuneration %(amount)s on table %(table)s.",
                    amount=base,
                    table=table.display_name,
                )
            )
        bracket = bracket[0]
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
        parcela = safe_eval(bracket.parcela_abater or "0", {"R": base})
        parcela += bracket.dependent_parcela * dependents
        # Despacho n.5-a + n.6: each dependent with a disability of 60%
        # or more adds the per-period amount by family situation,
        # optionally multiplied by the factor the employee declared.
        if disabled_dependents:
            parcela += (
                self._l10n_pt_disabled_dep_parcela(version, table)
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
            parcela += self._l10n_pt_pension_dep_parcela(version, table) * dependents
            # Despacho n.5-d / formula 3.c: armed forces disability adds
            # a flat amount on tables X and XI.
            if version.l10n_pt_military_disabled:
                parcela += bracket.forces_disabled_parcela
        retention = base * rate / 100.0 - parcela
        return float(math.floor(max(retention, 0.0)))

    def _l10n_pt_irs_withholding_table(self, version):
        self.ensure_one()
        table_variant = version.l10n_pt_irs_table_id
        if not table_variant:
            raise UserError(
                self.env._(
                    "Employee %(employee)s has no IRS withholding table "
                    "variant: set the IRS family status on the contract.",
                    employee=version.employee_id.name,
                )
            )
        # Overlapping sets are possible when a Despacho corrects part of
        # a period: the most recently effective set wins, and for equal
        # start dates the narrower (earlier-ending) window is preferred.
        table = self.env["hr.pt.irs.withholding.table"].search(
            [
                ("date_start", "<=", self.date_from),
                "|",
                ("date_end", "=", False),
                ("date_end", ">=", self.date_from),
                ("region", "=", version.l10n_pt_irs_region or "continente"),
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
                    date=self.date_from,
                    region=version.l10n_pt_irs_region or "continente",
                    variant=table_variant.code,
                )
            )
        return table

    def _l10n_pt_disabled_dep_parcela(self, version, table):
        # Despacho n.5-a: single workers and married workers filing
        # alone get the higher amount; joint filers get half of it.
        self.ensure_one()
        if version.l10n_pt_irs_family_status == "married_joint":
            return table.disabled_dep_parcela_joint
        return table.disabled_dep_parcela_single

    def _l10n_pt_pension_dep_parcela(self, version, table):
        # Despacho n.5-c for pension tables VIII-XI.
        self.ensure_one()
        status = version.l10n_pt_irs_family_status
        if status == "married_single_income":
            return table.pension_dep_parcela_single_income
        if status == "married_joint":
            return table.pension_dep_parcela_joint
        return table.pension_dep_parcela_single

    # IRS Jovem (art. 12-B CIRS): the exemption applies to income up to
    # 55 x IAS per year; payroll withholds on the non-exempt portion.
    # Despacho n.5-g caps the accumulated monthly exemptions at the
    # annual limit divided by 14, approximated here as a monthly cap.
    def _l10n_pt_irs_jovem_base(self, taxable, table):
        self.ensure_one()
        version = self.contract_id
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
        monthly_cap = 55.0 * (table.ias or 0.0) / 14.0
        exempt = min(taxable, monthly_cap) * exemption
        return taxable - exempt
