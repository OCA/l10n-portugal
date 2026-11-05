# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Portugal - IVA",
    "version": "20.0.1.0.0",
    "license": "LGPL-3",
    "author": "Daniel Reis, Odoo S.A., Odoo Community Association (OCA)",
    "summary": "Portuguese VAT requirements extensions",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Accounting/Localizations",
    "maintainers": ["dreispt"],
    "development_status": "Production/Stable",
    "depends": ["account", "l10n_pt"],
    "data": [
        "security/ir.access.csv",
        "data/vat_exempt_reason.xml",
        "data/vat_adjustment_norm.xml",
        "views/account_journal_view.xml",
        "views/account_move_view.xml",
        "views/account_tax_view.xml",
        "views/account_tax_group_view.xml",
        "views/l10n_pt_vat_exempt_reason_view.xml",
        "views/vat_adjustment_norm_view.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
}
