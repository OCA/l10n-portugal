# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tools import SQL
from odoo.tools.sql import column_exists, create_column

from .models.account_tax_group import L10N_PT_RATE_MAP


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


def preserve_legacy_vat(cr):
    """
    Snapshot each move's legacy exemption reason code into
    l10n_pt_legacy_vat_exemption_code (never overwrites).
    """
    if column_exists(cr, "account_move", "l10npt_vat_exempt_reason") and column_exists(
        cr, "account_l10n_pt_vat_exempt_reason", "code"
    ):
        if not column_exists(cr, "account_move", "l10n_pt_legacy_vat_exemption_code"):
            create_column(
                cr, "account_move", "l10n_pt_legacy_vat_exemption_code", "varchar"
            )
        cr.execute(
            """
            UPDATE account_move AS move
               SET l10n_pt_legacy_vat_exemption_code = reason.code
              FROM account_l10n_pt_vat_exempt_reason AS reason
             WHERE move.l10npt_vat_exempt_reason = reason.id
               AND move.l10n_pt_legacy_vat_exemption_code IS NULL
            """
        )


def apply_legacy_tax_regions(env):
    """
    Map legacy account.tax fiscal zone values onto the tax group PT
    region, only where every tax of the group agrees on a single
    non-default zone. Inferred Mainland defaults and conflicting zones
    are preserved.
    """
    for column in ("l10n_pt_fiscal_zone", "l10n_pt_fiscal_zone_old"):
        if column_exists(env.cr, "account_tax", column):
            break
    else:
        return
    rows = env.execute_query(
        SQL(
            """
            SELECT tax_group_id, array_agg(DISTINCT %s)
              FROM account_tax
             WHERE tax_group_id IS NOT NULL AND %s IS NOT NULL
             GROUP BY tax_group_id
            """,
            SQL.identifier(column),
            SQL.identifier(column),
        )
    )
    regions = {
        group_id: zones[0]
        for group_id, zones in rows
        if len(zones) == 1 and zones[0] in ("PT-MA", "PT-AC")
    }
    for group in (
        env["account.tax.group"]
        .browse(regions)
        .filtered(lambda group: group.country_code == "PT")
    ):
        group.l10n_pt_tax_region = regions[group.id]


def pre_init_hook(env):
    preserve_legacy_vat(env.cr)


def post_init_hook(env):
    _fill_tax_groups(env)
    apply_legacy_tax_regions(env)
