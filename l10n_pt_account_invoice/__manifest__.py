# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Portugal - Invoicing",
    "version": "20.0.1.0.0",
    "license": "LGPL-3",
    "author": "Daniel Reis, Odoo Community Association (OCA)",
    "summary": "Portuguese invoicing requirements",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Accounting/Localizations",
    "maintainers": ["dreispt"],
    "development_status": "Production/Stable",
    "depends": ["account", "l10n_pt"],
    "data": [
        "security/ir.access.csv",
        "data/vat_adjustment_norm.xml",
        "views/account_vat_adjustment_norm_views.xml",
        "views/account_move_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
}
