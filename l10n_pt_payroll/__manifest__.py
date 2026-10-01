# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Portugal - Payroll",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Daniel Reis, Odoo Community Association (OCA)",
    "summary": "Portuguese payroll base: salary structure and rules",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Payroll",
    "maintainers": ["dreispt"],
    "development_status": "Alpha",
    "depends": ["payroll", "l10n_pt_hr"],
    "data": [
        "data/hr_payroll_data.xml",
    ],
    "demo": ["demo/hr_payroll_demo.xml"],
    "installable": True,
    "auto_install": False,
}
