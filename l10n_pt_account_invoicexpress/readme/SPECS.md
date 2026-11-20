# InvoiceXpress VAT exemption mapping — spec

**Status:** in progress
**Date:** 2026-11-20
**Scope:** `l10n_pt_account_invoicexpress` (AGPL-3, this repo).
**Related:** `l10n_pt_account_vat` (#198) and `l10n_pt_invoice_provider`
(#193) — dependencies at the reviewed PR tips; `l10n_pt_vat` is not a
dependency.

## Context

The Odoo 20 port of this addon targets the new
`l10n_pt_invoice_provider` contract and the `l10n_pt_account_vat` tax
model. The legacy invoice-level exemption field is no longer a
dependency, so the document-level `tax_exemption` payload key must be
derived from the invoice lines' taxes instead.

## Spec

### Payload

- PT InvoiceXpress invoices and credit notes use the actual invoice
  product lines; section, subsection and note lines never enter the
  payload.
- InvoiceXpress accepts one tax per item and one exemption reason per
  document. When the product lines carry zero-rate taxes that all
  share a single distinct exemption M-code, that code is sent once as
  `invoice.tax_exemption`; zero-rate lines sharing the code may
  coexist with taxable lines. Documents whose lines are all taxed
  omit the key entirely.

### Validation

- Lines using different exemption codes are rejected with a
  `UserError` before any provider HTTP request is made for the
  document; the user must split the invoice.
- A zero-rate tax must have its exemption reason configured on the
  tax; there is no fallback to an unconfigured taxless item.
- A line with no tax, multiple taxes, or a tax group is rejected
  rather than silently reduced to the first tax.
- The form shows the computed exemption as a read-only, non-stored
  field derived from the lines — never from the historical snapshot.
  Posted/archived invoices are not modified, and no journal defaults
  are copied onto taxes.

### Migration

- Upgrading must preserve old document IDs, links and types even when
  the target `l10n_pt_doc_*` column already exists — the dependency
  can initialize those columns before this module's pre-migrate runs,
  so existing values are copied into the new column instead of only
  renamed.
- Journals already configured for InvoiceXpress get the provider
  selected only when no provider is set; already sent documents keep
  their provider document number, falling back to the original Odoo
  invoice name when missing.

## Non-goals

- Odoo 19 support, stock transport guides, or updating already-sent
  remote documents.

## Tasks

- [x] Spec the exemption derivation and validation rules.
- [x] Implement line-derived exemption code, payload key and
      pre-send validation.
- [x] Update view inheritance to the provider XMLIDs and show the
      computed exemption.
- [x] Update migration scripts for existing-column copies and
      provider backfill.
- [x] Extend tests: shared-code document payload, mixed-code
      rejection before HTTP, taxable-only omission.
- [x] Verify on a fresh disposable database: install + module tests,
      pre-commit.
