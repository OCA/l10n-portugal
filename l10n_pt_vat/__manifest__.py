# Copyright (C) 2021 Open Source Integrators (<http://www.opensourceintegrators.com>)
# Copyright (C) 2014 Sossia, Lda. (<http://www.sossia.pt>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Portugal - IVA",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Open Source Integrators, Sossia, Odoo Community Association (OCA)",
    "summary": "Portuguese VAT requirements extensions",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Accounting/Localizations",
    "maintainers": ["dreispt"],
    "development_status": "Production/Stable",
    "depends": ["account", "l10n_pt"],
    "data": [
        "security/ir.model.access.csv",
        "data/vat_exempt_reason.xml",
        "data/vat_adjustment_norm.xml",
        "views/account_journal_view.xml",
        "views/account_move_view.xml",
        "views/account_tax_view.xml",
        "views/l10n_pt_vat_exempt_reason_view.xml",
        "views/vat_adjustment_norm_view.xml",
    ],
    "installable": True,
    "auto_install": True,
}
