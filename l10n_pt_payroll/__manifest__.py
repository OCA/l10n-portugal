# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Portugal - Payroll",
    "version": "19.0.1.0.2",
    "license": "LGPL-3",
    "author": "Daniel Reis, Odoo Community Association (OCA)",
    "summary": "Portuguese payroll: salary structure and IRS retention",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Payroll",
    "maintainers": ["dreispt"],
    "development_status": "Alpha",
    "depends": ["payroll", "l10n_pt_hr", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/hr_payroll_data.xml",
        "views/hr_employee_views.xml",
        "views/hr_payslip_views.xml",
        "views/hr_salary_rule_views.xml",
        "views/hr_pt_irs_withholding_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/hr_pt_irs_withholding_import_views.xml",
        "wizard/hr_payroll_bank_account_add_views.xml",
    ],
    "demo": ["demo/hr_payroll_demo.xml"],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
}
