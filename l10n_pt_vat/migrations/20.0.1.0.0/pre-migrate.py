# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    # Preserve the legacy account.tax fiscal zone values;
    # they are mapped to account.tax.group.l10n_pt_tax_region post-migration.
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'account_tax'
           AND column_name = 'l10n_pt_fiscal_zone'
        """
    )
    if cr.fetchone():
        cr.execute(
            """
            ALTER TABLE account_tax
            RENAME COLUMN l10n_pt_fiscal_zone TO l10n_pt_fiscal_zone_old
            """
        )
