# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import SUPERUSER_ID, api

from odoo.addons.l10n_pt_account_vat.hooks import apply_legacy_tax_regions


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    apply_legacy_tax_regions(env)
