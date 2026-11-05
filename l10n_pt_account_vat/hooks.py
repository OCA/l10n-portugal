# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging

from .models.account_tax_group import L10N_PT_RATE_MAP

_logger = logging.getLogger(__name__)


def _fill_tax_groups(env):
    """
    Seed PT tax groups with the region and SAF-T tax category
    deduced from their tax rates, when they are uniform inside a group.
    """
    Tax = env["account.tax"]
    groups = env["account.tax.group"].search([("country_id.code", "=", "PT")])
    for group in groups:
        taxes = Tax.search([("tax_group_id", "=", group.id)])
        mapped = {L10N_PT_RATE_MAP.get(tax.amount) for tax in taxes}
        mapped.discard(None)
        if len(mapped) == 1:
            region, category = mapped.pop()
            group.write(
                {
                    "l10n_pt_tax_region": region,
                    "l10n_pt_tax_category": category,
                }
            )


def _legacy_zones(cr):
    """
    Map tax group ids to their legacy account.tax fiscal zones.
    Returns an empty dict if the l10n_pt_vat column is not there.
    """
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'account_tax'
           AND column_name = 'l10n_pt_fiscal_zone'
        """
    )
    if not cr.fetchone():
        return {}
    cr.execute(
        """
        SELECT tax_group_id, l10n_pt_fiscal_zone
          FROM account_tax
         WHERE tax_group_id IS NOT NULL
           AND l10n_pt_fiscal_zone IS NOT NULL
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
    reason = env.ref("l10n_pt_account_vat.M22", raise_if_not_found=False)
    if reason and reason.name == "Mercadorias à Consignação":
        reason.write(
            {
                "name": "IVA - não confere direito à dedução",
                "note": "Regime de tributação dos combustíveis líquidos"
                " aplicáveis aos revendedores"
                " - N.º 4 do art.º 72 do CIVA",
            }
        )


def _apply_legacy_zones(env, zones):
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


def pre_init_hook(env):
    """Take over data owned by the deprecated l10n_pt_vat module."""
    cr = env.cr
    cr.execute("SELECT 1 FROM ir_module_module WHERE name='l10n_pt_vat'")
    if not cr.fetchone():
        return
    # xmlids and records owned by the old module become ours
    cr.execute(
        "UPDATE ir_model_data"
        "   SET module='l10n_pt_account_vat'"
        " WHERE module='l10n_pt_vat'"
    )
    # dependencies on the old module now point to this one
    cr.execute(
        "UPDATE ir_module_module_dependency"
        "   SET name='l10n_pt_account_vat'"
        " WHERE name='l10n_pt_vat'"
    )
    cr.execute("DELETE FROM ir_module_module WHERE name='l10n_pt_vat'")


def post_init_hook(env):
    _fill_tax_groups(env)
    zones = _legacy_zones(env.cr)
    if zones:
        _apply_legacy_zones(env, zones)
        env.cr.execute("ALTER TABLE account_tax DROP COLUMN l10n_pt_fiscal_zone")
    _fix_m22_exempt_reason(env)
