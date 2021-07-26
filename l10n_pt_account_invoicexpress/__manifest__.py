# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Portugal InvoiceXpress Integration",
    "summary": "Legal invoices with InvoiceXpress",
    "version": "14.0.2.0.1",
    "author": "Open Source Integrators, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Accounting/Localizations/EDI",
    "maintainers": ["dreispt"],
    "development_status": "Production/Stable",
    "depends": ["l10n_pt_vat", "account"],
    "data": [
        "views/res_config_settings.xml",
        "views/account_tax_view.xml",
        "views/account_move_view.xml",
        "data/mail_template.xml",
        "data/res.country.csv",
    ],
    "application": True,
    "installable": True,
}
