# Copyright (C) 2021 Open Source Integrators (<http://www.opensourceintegrators.com>)
# Copyright (C) 2014 Sossia, Lda. (<http://www.sossia.pt>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Portugal - Legacy VAT Data",
    "version": "20.0.1.2.0",
    "license": "AGPL-3",
    "author": "Open Source Integrators, Daniel Reis, Sossia,"
    " Odoo Community Association (OCA)",
    "summary": "Preserve legacy Portuguese VAT data",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Accounting/Localizations",
    "maintainers": ["dreispt"],
    "development_status": "Production/Stable",
    "depends": ["account", "l10n_pt"],
    "data": [
        "security/ir.access.csv",
        "data/vat_exempt_reason.xml",
        "data/vat_adjustment_norm.xml",
    ],
    "installable": True,
    "auto_install": False,
}
