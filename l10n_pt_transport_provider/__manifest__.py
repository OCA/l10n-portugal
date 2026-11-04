# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Portugal - Transport Documents Provider",
    "summary": "Provider-agnostic certified transport documents on deliveries",
    "version": "20.0.1.0.0",
    "author": "Daniel Reis, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Inventory/Inventory",
    "maintainers": ["dreispt"],
    "development_status": "Production/Stable",
    "depends": ["l10n_pt_invoice_provider", "stock"],
    "data": [
        "views/stock_picking_type_view.xml",
        "views/stock_picking_view.xml",
    ],
    "installable": True,
}
