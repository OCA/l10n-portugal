# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Portugal InvoiceXpress Integration",
    "summary": "Portuguese certified invoices using InvoiceXpress",
    "version": "14.0.4.1.4",
    "author": "Open Source Integrators, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Accounting/Localizations/EDI",
    "maintainers": ["dreispt"],
    "development_status": "Production/Stable",
    "depends": ["l10n_pt_vat", "account"],
    "data": [
        "views/res_config_settings.xml",
        "views/account_journal_view.xml",
        "views/account_tax_view.xml",
        "views/account_move_view.xml",
        "views/res_company_view.xml",
        "views/res_country_view.xml",
        "data/mail_template.xml",
        "data/res.country.csv",
    ],
    "images": ["static/description/cover.png"],
    "application": True,
    "installable": True,
}
