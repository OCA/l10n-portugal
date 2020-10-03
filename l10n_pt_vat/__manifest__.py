# Copyright (C) 2014- Sossia, Lda. (<http://www.sossia.pt>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Portugal - IVA",
    "version": "12.0.0.1.0",
    "license": "AGPL-3",
    "depends": ["account", "l10n_pt"],
    "author": "Sossia, Odoo Community Association (OCA)",
    "summary": "Portuguese VAT requirements extensions",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Localisation/Portugal",
    "data": [
        "security/ir.model.access.csv",
        "data/vat_adjustment_norm.xml",
        "views/vat_adjustment_norm_view.xml",
        "views/account_invoice_view.xml",
    ],
    "installable": True,
    "auto_install": True,
}
