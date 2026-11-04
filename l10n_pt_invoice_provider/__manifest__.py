# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Portugal - Legal Documents Provider",
    "summary": "Provider-agnostic framework for Portuguese certified documents",
    "version": "20.0.1.0.0",
    "license": "AGPL-3",
    "maintainers": ["dreispt"],
    "development_status": "Production/Stable",
    "author": "Open Source Integrators, Daniel Reis, Odoo Community Association (OCA)",
    "category": "Accounting/Localizations/EDI",
    "website": "https://github.com/OCA/l10n-portugal",
    "depends": ["account"],
    "data": [
        "views/account_journal_view.xml",
        "views/account_move_view.xml",
    ],
    "installable": True,
}
