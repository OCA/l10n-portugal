# Copyright (C) 2026 Daniel Reis
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Portugal - Payroll SEPA",
    "summary": "Portuguese SEPA salary payment files",
    "version": "19.0.1.0.0",
    "license": "AGPL-3",
    "author": "Daniel Reis, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Payroll",
    "maintainers": ["dreispt"],
    "development_status": "Alpha",
    "depends": [
        "l10n_pt_payroll",
        "payroll_account",
        "account_banking_sepa_credit_transfer",
    ],
    "installable": False,
    "auto_install": False,
}
