# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.l10n_pt_account_vat.hooks import _fill_tax_groups

_logger = logging.getLogger(__name__)


def _legacy_zones(cr):
    """
    Map tax group ids to their legacy account.tax fiscal zones.
    Returns an empty dict if the column was not preserved by pre-migrate.
    """
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'account_tax'
           AND column_name = 'l10n_pt_fiscal_zone_old'
        """
    )
    if not cr.fetchone():
        return {}
    cr.execute(
        """
        SELECT tax_group_id, l10n_pt_fiscal_zone_old
          FROM account_tax
         WHERE tax_group_id IS NOT NULL
           AND l10n_pt_fiscal_zone_old IS NOT NULL
        """
    )
    zones = {}
    for group_id, zone in cr.fetchall():
        zones.setdefault(group_id, set()).add(zone)
    return zones


def _fix_m22_exempt_reason(env):
    # The M22 record was mislabeled as "Mercadorias à Consignação"
    # (which is actually M25). Relabel it to its official meaning,
    # unless the user already changed it.
    reason = env.ref("l10n_pt_vat.M22", raise_if_not_found=False)
    if reason and reason.name == "Mercadorias à Consignação":
        reason.write(
            {
                "name": "IVA - não confere direito à dedução",
                "note": "Regime de tributação dos combustíveis líquidos"
                " aplicáveis aos revendedores"
                " - N.º 4 do art.º 72 do CIVA",
            }
        )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Seed region and category from the PT rate map
    _fill_tax_groups(env)
    zones = _legacy_zones(cr)
    if zones:
        groups = (
            env["account.tax.group"]
            .browse(zones.keys())
            .filtered(lambda g: g.country_code == "PT")
        )
        for group in groups:
            legacy = zones[group.id]
            if len(legacy) > 1:
                _logger.warning(
                    "Conflicting legacy fiscal zones %s on tax group %s;"
                    " keeping inferred region %s",
                    sorted(legacy),
                    group.display_name,
                    group.l10n_pt_tax_region,
                )
                continue
            zone = next(iter(legacy))
            if zone == "PT" and group.l10n_pt_tax_region != "PT":
                # 'PT' was the old field's default, not a user choice;
                # keep the region inferred from the island rate.
                continue
            # A non-default legacy zone was set deliberately, keep it
            group.l10n_pt_tax_region = zone
        cr.execute("ALTER TABLE account_tax DROP COLUMN l10n_pt_fiscal_zone_old")
    _fix_m22_exempt_reason(env)
