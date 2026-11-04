# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

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


def post_init_hook(env):
    _fill_tax_groups(env)
