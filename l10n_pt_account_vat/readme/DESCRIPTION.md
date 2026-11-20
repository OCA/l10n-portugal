Add the Portuguese VAT data model that mirrors the Odoo work in
progress for the native Portuguese certification,
`l10n_pt_certification` (<https://github.com/odoo/odoo/pull/296355>):

- `account.tax.l10n_pt_tax_exemption_reason`: the legally accepted VAT
  exemption reason codes, required on Portuguese taxes with a 0%
  amount.
- `account.tax.group.l10n_pt_tax_region` and
  `l10n_pt_tax_category`: the VAT zone and SAF-T tax category, seeded
  automatically for the standard Portuguese chart of accounts.
- `account.move.l10n_pt_legacy_vat_exemption_code`: a read-only
  historical snapshot of the exemption codes stored by the retired
  ``l10n_pt_vat`` module, kept visible on upgraded databases.

This addon is a temporary bridge. Odoo's native Portuguese localization
is expected to replace its tax fields and validation once the upstream
changes are available. Before removing this addon, verify that any
historical exemption snapshots you need are preserved.

``l10n_pt_vat`` is not ported to Odoo 20: it keeps its legacy models
and catalog data so upgraded databases preserve them, and this module
exposes the historical exemption snapshot (see INSTALL.md).

The credit-note VAT adjustment legal basis catalog and selector live
in the optional ``l10n_pt_account_invoice`` addon.
