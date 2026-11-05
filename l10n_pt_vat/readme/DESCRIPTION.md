This module extends the base localization modules with VAT specific
functions that are required by the Portuguese Tax Authorities,
including:

- The use of pre-defined legally accepted reasons for issuing credit
  notes, as required for fields 40/41 of the VAT statement (Portaria nº
  255/2013).
- A document-level VAT exemption reason and the VAT adjustment norms.

The tax-level exemption reason on `account.tax` and the tax group
region/category fields are provided by the ``l10n_pt_account_vat``
dependency, which mirrors the data model of Odoo's
`l10n_pt_certification` WIP
(<https://github.com/odoo/odoo/pull/196102>) so that those fields can
be dropped once the core module lands.
