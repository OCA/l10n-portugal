# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Portugal Moloni Integration",
    "summary": "Portuguese certified invoices using Moloni",
    "version": "20.0.1.0.0",
    "author": "Daniel Reis, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Accounting/Localizations/EDI",
    "maintainers": ["dreispt"],
    "development_status": "Alpha",
    "depends": ["l10n_pt_account_vat", "l10n_pt_invoice_provider", "account"],
    "data": [
        "views/res_company_view.xml",
        "views/account_journal_view.xml",
    ],
    "application": True,
    "installable": True,
}
