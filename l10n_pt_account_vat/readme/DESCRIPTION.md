Add the Portuguese VAT data model that mirrors the Odoo work in
progress for the native Portuguese certification,
`l10n_pt_certification` (<https://github.com/odoo/odoo/pull/296355>):

- `account.tax.l10n_pt_tax_exemption_reason`: the legally accepted VAT
  exemption reason codes, required on Portuguese taxes with a 0%
  amount.
- `account.tax.group.l10n_pt_tax_region` and
  `l10n_pt_tax_category`: the VAT zone and SAF-T tax category, seeded
  automatically for the standard Portuguese chart of accounts.

This module only carries what the core module is expected to provide.
The remaining Portuguese VAT extensions — the VAT adjustment norms
(fields 40/41 of the VAT statement, Portaria nº 255/2013) and the
document-level VAT exemption reason — live in ``l10n_pt_vat``, which
depends on this module.
