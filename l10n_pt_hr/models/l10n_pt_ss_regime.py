# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class L10nPtSsRegime(models.Model):
    _name = "l10n.pt.ss.regime"
    _description = "Social Security Regime"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Stable technical code of the regime. Segurança Social does not "
        "publish numeric codes for regimes; this key identifies the "
        "situação contributiva in module data.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    l10n_pt_employee_rate = fields.Float(
        string="Employee Rate (%)",
        default=11.0,
        digits=(16, 4),
        help="TSU rate withheld from the employee's pay (trabalhador). "
        "The default matches the general regime (11%).",
    )
    l10n_pt_employer_rate = fields.Float(
        string="Employer Rate (%)",
        default=23.75,
        digits=(16, 4),
        help="TSU rate paid by the employer (entidade patronal). The "
        "default matches the general regime (23.75%).",
    )
    l10n_pt_total_rate = fields.Float(
        string="Total Rate (%)",
        compute="_compute_l10n_pt_total_rate",
        digits=(16, 4),
        help="Taxa global: employee plus employer contribution rate.",
    )
    l10n_pt_dr_code = fields.Char(
        string="DR Rate Code",
        help="Codigo de taxa na DR of the official Seguranca Social "
        "contribution-rate table, used by the monthly remuneration "
        "declaration (DMR). Employers with a specific code assigned "
        "by Seguranca Social use it instead on the declaration.",
    )

    @api.depends("l10n_pt_employee_rate", "l10n_pt_employer_rate")
    def _compute_l10n_pt_total_rate(self):
        for regime in self:
            regime.l10n_pt_total_rate = (
                regime.l10n_pt_employee_rate + regime.l10n_pt_employer_rate
            )
