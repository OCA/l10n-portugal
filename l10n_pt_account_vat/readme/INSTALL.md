**Fresh installation**

Install the module normally once the database runs an upgraded,
compatible Odoo 20 community core:

```bash
odoo-bin -d <database> -i l10n_pt_account_vat --stop-after-init
```

Take a backup before any upgrade on a production database.

**Upgrading an existing database**

`l10n_pt_vat` keeps its legacy models and catalog data on Odoo 20
but no longer provides the replacement features. After the
compatible Odoo 20 core upgrade, update the installed legacy module
first on an upgrade copy of the database:

```bash
odoo-bin -d <upgrade-copy> -u l10n_pt_vat --stop-after-init
```

Installing `l10n_pt_vat` does not install this module automatically;
install or update it separately:

```bash
odoo-bin -d <upgrade-copy> -i l10n_pt_account_vat --stop-after-init
```

(or `-u l10n_pt_account_vat` when it is already installed)

This update snapshots the historical exemption codes stored by the
legacy module into the read-only "Historical VAT Exemption Code"
field and maps the legacy tax fiscal zones onto the tax group
regions. No data is deleted and no tax is rewritten; the raw legacy
columns and the `account_l10n_pt_vat_exempt_reason` table remain in
the database.

Install `l10n_pt_account_invoice` afterwards if you need the VAT
adjustment legal basis selector; it copies the legacy norms into its
own records. You can install it later; neither upgrade removes
existing adjustment norms or their links to credit notes.

Uninstalling `l10n_pt_vat` is optional and only after verifying the
successor data; its original records then remain removable without
affecting the successors.

This step does not replace the normal Odoo major-version upgrade of
`base` and the other modules — chain it with the platform's usual
upgrade procedure.
