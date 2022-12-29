# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Portugal InvoiceXpress Legal Transport Documents",
    "summary": "Portuguese legal transport and shipping documents"
    " (Guias de Transporte e Guias de Remessa) generated with InvoiceXpress",
    "version": "14.0.3.0.1",
    "author": "Open Source Integrators, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Accounting/Localizations/EDI",
    "maintainers": ["dreispt"],
    "development_status": "Production/Stable",
    "depends": ["l10n_pt_account_invoicexpress", "sale_stock"],
    "data": [
        "views/res_company_view.xml",
        "views/res_config_settings.xml",
        "views/stock_picking_view.xml",
        "views/stock_picking_type_view.xml",
        "data/mail_template.xml",
    ],
    "images": ["static/description/cover.png"],
    "installable": True,
    "auto_install": True,
}
