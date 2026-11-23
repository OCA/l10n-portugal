# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Portugal - Human Resources",
    "version": "19.0.1.0.1",
    "license": "LGPL-3",
    "author": "Daniel Reis, Odoo Community Association (OCA)",
    "summary": "Portuguese HR demo data and master data lists",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Human Resources",
    "maintainers": ["dreispt"],
    "development_status": "Alpha",
    "depends": ["hr", "l10n_pt"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/l10n_pt_ss_regime.xml",
        "data/l10n_pt_irs_table.xml",
        "data/l10n_pt_work_time_arrangement.xml",
        "views/l10n_pt_hr_views.xml",
        "views/l10n_pt_establishment_views.xml",
        "views/hr_employee_views.xml",
    ],
    "demo": ["demo/hr_employee_demo.xml"],
    "installable": True,
    "auto_install": False,
}
