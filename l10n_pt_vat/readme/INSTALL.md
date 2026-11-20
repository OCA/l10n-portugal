**Upgrading an existing database**

After the compatible Odoo 20 core upgrade, update the installed
`l10n_pt_vat` module on an upgrade copy of the database:

```bash
odoo-bin -d <upgrade-copy> -u l10n_pt_vat --stop-after-init
```

Then install or update the successor addons separately:

```bash
odoo-bin -d <upgrade-copy> -i l10n_pt_account_vat,l10n_pt_account_invoice --stop-after-init
```

Only uninstall `l10n_pt_vat` after verifying the copied data in the
successors; its original records then remain removable without
affecting them. This module is not for new deployments and has no
dependency on either successor.
