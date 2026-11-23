# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import math
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import date_utils, float_round, format_amount, formatLang


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    payment_date = fields.Date(
        copy=False,
        help="Date the income is paid or made available. If blank, IRS uses the "
        "payslip period end.",
    )

    def copy(self, default=None):
        if default and default.get("credit_note"):
            default = {"payment_date": self.payment_date, **default}
        return super().copy(default)

    @api.constrains("state", "payment_date", "date_to")
    def _check_l10n_pt_irs_payment_order(self):
        starter = self.env.ref(
            "l10n_pt_payroll.hr_rule_pt_irs", raise_if_not_found=False
        )
        if not starter:
            return
        regular = self.filtered(
            lambda slip: slip.state == "done"
            and not slip.credit_note
            and starter in slip.line_ids.salary_rule_id
        )
        seen = set()
        for slip in regular:
            key = (
                slip.employee_id.id,
                slip.company_id.id,
                date_utils.start_of(slip._l10n_pt_irs_payment_date(), "month"),
            )
            if key in seen:
                raise ValidationError(
                    self.env._(
                        "Confirm IRS payslips for the same employee and month "
                        "separately."
                    )
                )
            seen.add(key)
        for slip in regular:
            slip._get_payroll_history_lines(
                ("IRS",),
                date_basis="payment",
                window="month_to_date",
                strict=True,
                require_payment_dates=True,
            )

    def _l10n_pt_ss_line_values(self, name, base, rate):
        result_name = self.env._(
            "%(name)s (%(rate)s%%)",
            name=name,
            rate=formatLang(self.env, rate, digits=4),
        )
        digits = self.env["decimal.precision"].precision_get("Payroll")
        rate_digits = self.env["decimal.precision"].precision_get("Payroll Rate")
        total = base * rate / 100.0
        displayed_total = (
            float_round(base, precision_digits=digits)
            * float_round(rate, precision_digits=rate_digits)
            / 100.0
        )
        if float_round(total, precision_digits=digits) != float_round(
            displayed_total, precision_digits=digits
        ):
            return (
                total,
                100.0,
                self.env._(
                    "%(name)s - Contribution base: %(base)s",
                    name=result_name,
                    base=format_amount(
                        self.env, abs(base), self.company_id.currency_id
                    ),
                ),
            )
        return base, rate, result_name

    def _l10n_pt_irs_line_name(self, name, details):
        currency = self.company_id.currency_id
        base = details["base"]
        taxable = details["taxable"]
        name = self.env._(
            "%(name)s - Taxable base: %(base)s",
            name=name,
            base=format_amount(self.env, base, currency),
        )
        if taxable > base and taxable > 0:
            name = self.env._(
                "%(name)s (income before relief: %(amount)s)",
                name=name,
                amount=format_amount(self.env, taxable, currency),
            )
        if details.get("allowance_applied"):
            name = self.env._(
                "%(name)s; single-payer allowance applied: %(allowance)s",
                name=name,
                allowance=format_amount(
                    self.env, details["allowance_applied"], currency
                ),
            )
        if details["rate"] is not None:
            name = self.env._(
                "%(name)s; applied rate: %(rate)s%%; formula deductions: %(deduction)s",
                name=name,
                rate=formatLang(self.env, details["rate"], digits=3),
                deduction=format_amount(self.env, details["parcela"], currency),
            )
        if details.get("has_previous"):
            name = self.env._(
                "%(name)s; month-to-date withholding: %(monthly)s; "
                "previously withheld: %(previous)s",
                name=name,
                monthly=format_amount(self.env, details["month_amount"], currency),
                previous=format_amount(
                    self.env, details["prior_withholding"], currency
                ),
            )
        if taxable > 0:
            name = self.env._(
                "%(name)s; monthly effective withholding rate: %(effective)s%%",
                name=name,
                effective=formatLang(
                    self.env, details["month_amount"] * 100.0 / taxable, digits=2
                ),
            )
        return name

    def _l10n_pt_irs_retention_details(self, current, allowance):
        self.ensure_one()
        version = self.contract_id
        if not version:
            raise UserError(self.env._("The payslip has no contract."))
        previous = self.env["hr.payslip.line"]
        if not self.credit_note:
            previous = self._get_payroll_history_lines(
                ("IRS",),
                date_basis="payment",
                window="month_to_date",
                strict=True,
                require_payment_dates=True,
            )
        prior_withholding = -sum(previous.mapped("total"))
        prior_taxable, prior_allowance = self._l10n_pt_irs_prior_amounts(previous)
        details = self.env["hr.pt.irs.withholding.table"]._calculate_withholding(
            version,
            self._l10n_pt_irs_payment_date(),
            current + prior_taxable,
            allowance=allowance,
            previous_allowance=prior_allowance,
        )
        month_amount = details["amount"]
        if (
            self.company_id.currency_id.compare_amounts(month_amount, prior_withholding)
            < 0
        ):
            raise UserError(
                self.env._(
                    "IRS already withheld exceeds the recalculated monthly amount. "
                    "Review the earlier payslips before continuing."
                )
            )
        details.update(
            amount=month_amount - prior_withholding,
            month_amount=month_amount,
            prior_withholding=prior_withholding,
            has_previous=bool(previous),
        )
        return details

    def _l10n_pt_irs_payment_date(self):
        self.ensure_one()
        return self.payment_date or self.date_to

    # TODO: Move payroll history selection and totals into OCA Payroll as a
    # generic feature. Keep Portuguese withholding and subsidy policy here.
    def _get_payroll_history_totals(
        self, codes, *, date_basis, window, months=None, strict=False
    ):
        """Return signed historical totals by salary rule code, zero if absent.

        Sum finalized lines for this employee and employer across contract
        versions. Exclude this payslip and reverse the sign of credit notes.

        Use ``date_basis="payment"`` for the payment date (falling back to the
        period end), or ``"period"`` for the period end. ``month_to_date`` and
        ``year_to_date`` include the anchor date. ``previous_months`` requires a
        positive ``months`` count and excludes the anchor month. In strict
        mode, reject reversals and finalized entries later in the anchor
        month or year for to-date windows.
        """
        by_code = dict.fromkeys(codes, 0.0)
        recorded = defaultdict(list)
        for line in self._get_payroll_history_lines(
            by_code, date_basis=date_basis, window=window, months=months, strict=strict
        ):
            recorded[line.code].append(
                -line.total if line.slip_id.credit_note else line.total
            )
        return {code: math.fsum(recorded[code]) for code in by_code}

    def _get_payroll_history_lines(
        self,
        codes,
        *,
        date_basis,
        window,
        months=None,
        strict=False,
        require_payment_dates=False,
    ):
        """Return finalized lines in the requested window without aggregating
        them, applying the strict ordering and explicit-date checks."""
        self.ensure_one()
        if date_basis == "payment":
            anchor = self.payment_date or self.date_to
        elif date_basis == "period":
            anchor = self.date_to
        else:
            raise ValueError("Unknown payroll history date basis")
        if window == "previous_months":
            if type(months) is not int or months <= 0:
                raise ValueError("Previous months requires a positive integer")
            month_start = date_utils.start_of(anchor, "month")
            start = date_utils.subtract(month_start, months=months)
            end = date_utils.subtract(month_start, days=1)
        elif window in ("month_to_date", "year_to_date") and months is None:
            unit = "month" if window == "month_to_date" else "year"
            start, end = date_utils.start_of(anchor, unit), anchor
        else:
            raise ValueError("Invalid payroll history window")
        search_end = (
            date_utils.end_of(anchor, unit)
            if strict and window != "previous_months"
            else end
        )
        date_domain = Domain("date_to", ">=", start) & Domain(
            "date_to", "<=", search_end
        )
        if date_basis == "payment":
            date_domain = (
                Domain("payment_date", ">=", start)
                & Domain("payment_date", "<=", search_end)
            ) | (Domain("payment_date", "=", False) & date_domain)
        slips = self.env["hr.payslip"].search(
            date_domain
            & Domain(
                [
                    ("id", "!=", self.id),
                    ("state", "=", "done"),
                    ("employee_id", "=", self.employee_id.id),
                    ("company_id", "=", self.company_id.id),
                ]
            )
        )
        lines = self.env["hr.payslip.line"].search(
            Domain("slip_id", "in", slips.ids) & Domain("code", "in", list(codes))
        )
        if (
            require_payment_dates
            and lines
            and (
                not self.payment_date
                or any(not slip.payment_date for slip in lines.slip_id)
            )
        ):
            raise ValidationError(
                self.env._(
                    "Set a payment date on each payslip when there is more than "
                    "one payment in the window."
                )
            )
        if strict:
            for slip in lines.slip_id:
                history_date = (
                    (slip.payment_date or slip.date_to)
                    if date_basis == "payment"
                    else slip.date_to
                )
                if slip.credit_note or history_date > end:
                    raise UserError(
                        self.env._(
                            "Review payroll history manually before processing "
                            "a backdated payment or a reversal."
                        )
                    )
        return lines

    def _l10n_pt_irs_prior_amounts(self, withholding_lines):
        taxable = allowance = 0.0
        if not withholding_lines:
            return taxable, allowance
        base_rule = self.env.ref("l10n_pt_payroll.hr_rule_pt_irs_base")
        allowance_rule = self.env.ref("l10n_pt_payroll.hr_rule_pt_irs_allowance")
        for line in withholding_lines:
            recorded = line.slip_id.line_ids.filtered(
                lambda item, contract=line.contract_id: item.contract_id == contract
            )
            bases = recorded.filtered(lambda item: item.salary_rule_id == base_rule)
            allowances = recorded.filtered(
                lambda item: item.salary_rule_id == allowance_rule
            )
            if len(bases) != 1 or len(allowances) != 1:
                raise UserError(
                    self.env._(
                        "An earlier payslip has no unique record of its IRS taxable "
                        "base and allowance. Review the monthly withholding before "
                        "processing another payslip."
                    )
                )
            taxable += bases.total
            allowance += allowances.total
        return taxable, allowance

    def _l10n_pt_irs_current_taxable(self, result_rules, version):
        structure = self.struct_id or version.struct_id
        taxable = 0.0
        for rule in structure.get_all_rules():
            if (
                rule.l10n_pt_irs_taxable
                and rule.code
                and rule.code != "IRS"
                and rule.code in result_rules.dict
            ):
                taxable += result_rules.dict[rule.code].total * rule.l10n_pt_irs_taxable
        return self._l10n_pt_irs_round_input(taxable)

    def _l10n_pt_irs_current_allowance(self, taxable, version):
        allowance = self._l10n_pt_irs_round_input(
            self._l10n_pt_irs_single_payer_amount(version)
        )
        return min(max(taxable, 0.0), allowance)

    def _l10n_pt_irs_round_input(self, amount):
        return float_round(
            amount,
            precision_digits=self.env["decimal.precision"].precision_get("Payroll"),
        )

    def _l10n_pt_irs_single_payer_amount(self, version):
        allowance_inputs = self.input_line_ids.filtered(
            lambda line: line.code == "PT_IRS_SINGLE_PAYER"
            and line.contract_id == version
        )
        if len(allowance_inputs) > 1:
            raise UserError(
                self.env._("Enter only one single-payer allowance per contract.")
            )
        allowance = allowance_inputs.amount if allowance_inputs else 0.0
        if not math.isfinite(allowance) or allowance < 0:
            raise UserError(
                self.env._("The single-payer allowance must be non-negative.")
            )
        return allowance
