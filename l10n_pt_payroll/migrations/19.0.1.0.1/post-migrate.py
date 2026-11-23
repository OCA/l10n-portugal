# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import SUPERUSER_ID, api

RULES = {
    "basic": ("BASIC", "income"),
    "gross": ("GROSS", "ignore"),
    "ss": ("SS", "contribution"),
    "irs": ("IRS", "withholding"),
    "ss_company": ("SS_COMP", "ignore"),
    "sat": ("SAT_COMP", "ignore"),
    "net": ("NET", "ignore"),
}
LEGACY_RATE = (
    "(contract.l10n_pt_ss_regime_id or "
    "contract.env.ref('l10n_pt_hr.l10n_pt_ss_regime_geral', "
    "raise_if_not_found=False)).l10n_pt_%s_rate / 100"
)
LEGACY_FORMULAS = {
    "SS": "result = -categories.BASIC * " + LEGACY_RATE % "employee",
    "SS_COMP": "result = categories.BASIC * " + LEGACY_RATE % "employer",
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for suffix, (code, role) in RULES.items():
        rule = env.ref(f"l10n_pt_payroll.hr_rule_pt_{suffix}", raise_if_not_found=False)
        if not rule or rule.code != code:
            continue
        vals = {}
        if not rule.l10n_pt_dmr_at_role and (
            code != "BASIC" or rule.l10n_pt_dmr_code in (False, "A")
        ):
            vals["l10n_pt_dmr_at_role"] = role
        if code == "BASIC":
            if not rule.l10n_pt_dmr_code:
                vals["l10n_pt_dmr_code"] = "A"
            if not rule.l10n_pt_ss_nature_code:
                vals["l10n_pt_ss_nature_code"] = "P"
        formula = rule.amount_python_compute or ""
        if code in LEGACY_FORMULAS and formula.strip() == LEGACY_FORMULAS[code]:
            vals["amount_python_compute"] = formula.replace(
                "categories.BASIC",
                "result_rules.dict['PT_SS_BASE'].total",
            )
        if vals:
            rule.write(vals)
