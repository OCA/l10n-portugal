# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Portugal InvoiceXpress Transport Documents",
    "summary": "Legal trsanport documents generated with InvoiceXpress",
    "version": "14.0.1.1.0",
    "author": "Open Source Integrators, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Accounting/Localizations/Account Charts",
    "maintainers": ["dreispt"],
    "development_status": "Production/Stable",
    "depends": ["l10n_pt_account_invoicexpress", "sale_stock"],
    "data": [
        "data/ir_config_parameter.xml",
        "views/stock_picking_view.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": True,
}
