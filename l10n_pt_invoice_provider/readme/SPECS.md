# Provider invoice PDF — spec

**Status:** in progress **Date:** 2026-11-21 **Scope:** `l10n_pt_invoice_provider` —
`account.move` invoice PDF rendering and Send & Print paths. **Related:** —

## Context

Customer invoices issued through a legal document provider (InvoiceXpress and future
providers) already have an official PDF that the provider manages. Letting Odoo render
its own PDF for those moves would produce a non-official copy that could be printed or
sent to the customer. Portuguese customer invoices without any provider still need a
printable document, but it is not a fiscal document, so it must be labeled as a
proforma.

## Spec

### Provider-backed documents never get an Odoo PDF

- Applies to posted `out_invoice` and `out_refund` moves that have
  `l10n_pt_doc_provider_id` set or `l10n_pt_doc_id` set — that is, moves assigned to a
  legal provider or already linked to an issued document.
- Covers both entry points:
  - direct report Print (`ir.actions.report`, `account.account_invoices`);
  - Send & Print (`account.move.send._generate_and_send_invoices`), including the
    proforma fallback path.
- Only a PDF fetched from the provider and linked as the move's official document may be
  used. PDFs that Odoo generated earlier for the move are not trusted.
- The core invoice PDF remains the only PDF link. The attachment records its source
  provider. Reuse it only when that code matches the invoice's provider. If retrieval
  succeeds, replace the official PDF link but keep the previous file as an attachment.
- When no PDF is cached, fetch it remotely by `l10n_pt_doc_id` through the provider's
  `get_document_pdf`.
- A provider move without `l10n_pt_doc_id` blocks before any fetch or issuance — there
  is no remote document to fetch.
- Provider PDF unavailable is a retryable error: no local rendering, no sending and no
  proforma fallback for that move. Issuance that already completed is not rolled back.
- Draft moves and moves without a provider keep standard Odoo behavior.

### Portuguese invoices without provider render as proforma

- A posted `out_invoice` on a Portuguese journal (fiscal country PT) with no provider
  assigned or configured and no `l10n_pt_doc_id` renders through the native Odoo report
  with the proforma title.
- Excluded from this rule: non-PT journals, drafts, credit notes (`out_refund`) and any
  provider-backed move. Those keep the standard titles. Provider-backed moves are never
  labeled proforma.

### Eager fetch at posting

- Posting may attempt the provider PDF fetch right after document issuance, but a
  missing or unavailable PDF must not roll back the successfully issued legal document.

### Provider defaults are a creation-time snapshot

- New sale documents copy the journal's provider (including none) and document type
  when they are created. Values passed explicitly or through context defaults win.
  Posted and cancelled documents keep their stored values; journal edits never
  rewrite them.
- Changing a journal's provider refreshes the provider and type of unissued draft
  invoices and credit notes on that journal whose provider differs. Drafts that
  already match, posted documents and issued documents are untouched. Other journal
  edits do not refresh document defaults.

### Posting requires the journal's provider

- A draft customer invoice or credit note whose stored `l10n_pt_doc_provider_id`
  (including none) differs from its journal's configured provider cannot be
  posted. The check runs before posting and before any provider request, so a
  mismatched move never reaches document issuance.
- Soft posting may still queue future-dated moves; the check applies when a move
  is actually due, not when it is scheduled.

### Provider registry records

- Provider identity is a durable `l10n_pt.invoice.provider.record` row with an
  immutable stable code and a stable database ID. Journals and documents
  reference the record; the code remains the adapter identity used for provider
  lookups.
- A journal may only select an installed implementation: the selector lists
  records whose code resolves to a loaded adapter, and records cannot be created
  or opened manually.
- Historical records survive adapter uninstallation. Issued documents keep
  printing their cached provider PDF without errors even when the adapter is
  gone; only an uncached PDF fetch reports the missing adapter.
- Posting a draft sale document that still references a removed adapter is
  blocked before issuance and before any external provider request.
- This is the first 20.0 release of the framework; there is no migration from
  the unreleased selection-based prototype.

### Legal document download resolves the provider PDF

- `_get_invoice_legal_documents_all` (portal download) and
  `_get_invoice_legal_documents("pdf")` (direct download) resolve the provider PDF
  first for provider-backed moves, then delegate to `super()` so extra formats are
  preserved. A missing provider PDF raises the retryable error — there is no
  provider fallback to a local render.

### Provider boundary

- The InvoiceXpress adapter (#200 work) supplies `get_document_pdf` and remains
  unchanged. This spec defines framework behavior only.

## Decisions

- 2026-11-21: Provider and document type are snapshotted at creation instead of being
  recomputed from the journal while drafting (supersedes the earlier draft-recompute
  design). Journal provider changes explicitly refresh only unissued drafts, so
  posted and issued documents always keep the values they were created with.
- 2026-11-22: Provider identity moves from a transient selection string to durable
  `l10n_pt.invoice.provider.record` rows so history survives adapter uninstallation.

## Non-goals

- Changes to provider adapters or to the document issuance flow.

## Tasks

- [x] Write this spec
- [x] Add regression tests (`tests/test_provider_invoice_pdf.py`)
- [x] Implement provider PDF policy and PT proforma rule
- [x] Green round on `l10n-pt-provider-pdf-verify`
