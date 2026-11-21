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
- Reject any product line with a negative unit price or quantity
  before customer or tax synchronization, even if the document total
  is positive.
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

### Journal-level InvoiceXpress settings

- InvoiceXpress settings — account name, API key and email template — are set
  on each sales journal and are only visible while the journal's legal
  document provider is InvoiceXpress. The API key is restricted to accounting
  administrators. Account name and API key are not mandatory in the UI, so a
  journal can select the provider before its configuration is finished; API
  calls fail with a clear error until both are set.
- Document, customer and tax API requests use the invoice journal's account
  name as the API subdomain and authenticate with the journal's API key. The
  company keeps no InvoiceXpress settings.
- The email template is optional and explicit: without one the provider
  email action is unavailable, and a fresh journal can select the shipped
  default template. Odoo Send & Print remains the default and sends the
  provider PDF. Selecting a template enables the separate Email via
  Provider button for issued invoices; posting does not send email through
  InvoiceXpress. Clearing the template disables the provider action again.
- Provider availability requires the journal's account name, API key and
  document type plus a Portuguese company country; checking it never calls
  the API.
- On upgrade, former company-level settings are copied onto journals that
  use InvoiceXpress or have historical InvoiceXpress documents, without
  replacing values already set on journals.

### Provider registration

- The adapter self-registers through the framework's
  `l10n_pt.invoice.provider.record._register_provider("invoicexpress")`
  from its `post_init_hook` on install. On upgrade from Odoo 19.0, the
  `20.0.1.0.0` post-migration registers it before moving the legacy
  references and settings.
- Journals and documents reference the durable provider record; the
  framework record is retained when this adapter is uninstalled, so issued
  documents keep their provider identity and cached PDFs.
- The journal selector only offers providers whose adapter is installed;
  view conditions compare the related `invoicexpress_provider_code`
  (`l10n_pt_doc_provider_id.code`) instead of the old selection string.

### Debit notes

- Customer debit notes come from Odoo's standard Debit Note wizard on a
  posted invoice; the resulting `out_invoice` carries
  `debit_origin_id`, and the adapter reports the `debit_note` document
  type so documents post to `debit_notes.json` and finalize through the
  same change-state call.
- An original issued by the same InvoiceXpress account sends
  `invoice.owner_invoice_id` with the remote document ID; any other
  posted original sends `invoice.raw_owner_invoice` with the original
  document number or local name — never the wizard reference, which
  may include the reason text.
- A debit note whose original was issued by a different InvoiceXpress
  account is rejected before any provider request.
- Debit notes are only created for new documents; already-posted
  invoices are not remapped or reissued.

### Document PDF

- Printing or sending an issued invoice asks InvoiceXpress for the
  certified PDF through `GET api/pdf/<document id>.json`, then downloads
  the signed URL in `output.pdfUrl`. A `202` (still generating), a
  missing or malformed payload, or an unverifiable URL surfaces the
  framework's retryable "PDF unavailable" error — never a substitute
  document.
- The download URL must use HTTPS without credentials on the default
  port and live on an `*.invoicexpress.com` host or the exact
  InvoiceXpress documents S3 bucket host; it is fetched directly with
  redirects disabled and the API key is never forwarded. Only content
  starting with `%PDF-` is accepted.
- The first successful download is stored as the invoice's reference
  document; later prints reuse it without further provider requests.

## Roadmap

- Consider mapping eligible negative discount lines to InvoiceXpress's
  fixed document discount. Only do so if the tax bases, VAT, currency
  rounding and document totals are unchanged.

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
