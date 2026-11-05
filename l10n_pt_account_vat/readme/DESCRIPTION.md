This module replaces ``l10n_pt_vat`` and migrates databases
from it automatically (module data, xmlids and the legacy
``account.tax`` fiscal zone column).

This modules extends the base localization modules with a few VAT
specific functions that are required by the Portuguese Tax Authorities,
including:

- The use of pre-defined legally accepted reasons for issuing credit
  notes, as required for fields 40/41 of the VAT statement (Portaria nº
  255/2013).

NOTE: Odoo is implementing native Portuguese certification in
`l10n_pt_certification` (<https://github.com/odoo/odoo/pull/196102>),
which should replace the overlapping parts of this module once it is
released. To ease that future transition, this module deliberately
mirrors the projected data model — same field names and values on
`account.tax` (`l10n_pt_tax_exemption_reason`) and `account.tax.group`
(`l10n_pt_tax_region`, `l10n_pt_tax_category`) — so adopting the core
module should mean dropping duplicated fields rather than migrating
data. What has no core counterpart — the VAT adjustment norms and the
document-level VAT exemption reason — is expected to remain here.

Authorship: the tax exemption reason and tax group region/category
fields mirror Odoo's ``l10n_pt_certification`` WIP
(<https://github.com/odoo/odoo/pull/196102>) and carry Odoo S.A.
copyright; they will be dropped when that module reaches core. The
VAT adjustment norms, document-level exemption reason and all
migration code are OCA extensions copyrighted by Daniel Reis only.
