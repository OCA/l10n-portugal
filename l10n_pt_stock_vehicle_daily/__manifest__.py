# Copyright 2024 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Transport Documents for Vehicle Stock",
    "summary": "Daily documente with vehicle content, "
    "to communicate to Portuguese Tax Authorities",
    "website": "https://github.com/OCA/l10n-portugal",
    "license": "AGPL-3",
    "author": "Luz de Airbag, Open Source Integrators, Odoo Community Association (OCA)",
    "category": "Warehouse",
    "version": "14.0.1.1.0",
    "depends": [
        "stock_move_location",  # from OCA/stock-logistics-warehouse
    ],
    "data": [
        "views/stock_location_views.xml",
        "views/stock_picking_views.xml",
        "wizard/stock_move_location_views.xml",
    ],
}
