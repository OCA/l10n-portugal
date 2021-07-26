# Copyright (C) 2021 Open Source Integrators (<http://www.opensourceintegrators.com>)
# Copyright (C) 2014 Sossia, Lda. (<http://www.sossia.pt>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Portugal - IVA",
    "version": "14.0.1.0.0",
    "license": "AGPL-3",
    "depends": ["account", "l10n_pt"],
    "author": "Open Source Integrators, Sossia, Odoo Community Association (OCA)",
    "summary": "Portuguese VAT requirements extensions",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Accounting/Localizations",
    "data": [
        "security/ir.model.access.csv",
        "data/account.l10n_pt.vat.exempt.reason.csv",
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
