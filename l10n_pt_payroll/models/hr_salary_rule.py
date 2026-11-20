# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    l10n_pt_irs_taxable = fields.Float(
        string="IRS Taxable Share",
        default=0.0,
        help="Share of the rule total that enters the taxable "
        "remuneration R used by the Portuguese IRS retention "
        "computation: 1.0 means fully taxable, 0.5 half, 0.0 exempt. "
        "Use it for partially taxable payments such as the taxable "
        "portion of allowances.",
    )
    l10n_pt_dmr_code = fields.Char(
        string="DMR Earning Code",
        help="Official code de rendimento used by the Declaração "
        "Mensal de Remunerações (DMR) for the remuneration this "
        "rule produces. Leave empty for deduction rules; the code "
        "table is published by Segurança Social / AT.",
    )
