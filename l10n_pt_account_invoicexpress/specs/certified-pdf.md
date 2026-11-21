# Certified PDF — spec

- **Status:** implemented locally, verified
- **Date:** 2026-11-21
- **Scope:** `l10n_pt_account_invoicexpress` on Odoo 19
- **Related:** [OCA/l10n-portugal#200](https://github.com/OCA/l10n-portugal/pull/200)

## Context

InvoiceXpress issues the legal document and its certified PDF on its side. Before this
change, Odoo could only render its own layout for Print, Send & Print and portal
downloads, even for documents InvoiceXpress issued. Historical invoices that retain
their `invoicexpress_id` can retrieve the certified PDF without reissuing the document.

## Spec

- Applies only to posted `out_invoice`/`out_refund` moves that have an
  `invoicexpress_id`, independent of the journal's current InvoiceXpress toggle. All
  other documents keep the native Odoo PDF behavior.
- The certified PDF is fetched on demand — never at posting time.
- Retrieval asks InvoiceXpress for metadata through
  `GET api/pdf/<invoicexpress_id>.json`, then downloads the signed URL in
  `output.pdfUrl`.
- A `202` (still generating), a missing/malformed payload, an unverifiable URL, a
  non-PDF download or an upstream failure surfaces a retryable "PDF unavailable"
  `UserError`. No substitute document is produced.
- The download URL must use HTTPS without credentials on the default port and live on an
  `*.invoicexpress.com` host or the exact InvoiceXpress documents S3 bucket host. It is
  fetched directly with redirects disabled and the API key is never forwarded. Only
  content starting with `%PDF-` is accepted.
- The first successful download is stored as the invoice's reference document
  (`invoice_pdf_report_file` attachment flagged `invoicexpress_certified_pdf`). Later
  prints reuse it without further provider requests.
- A previously stored unmarked attachment (locally rendered PDF) is kept as an ordinary
  file — its `res_field` link is cleared only after a successful certified fetch.
- Print (`ir.actions.report`), Send & Print (`account.move.send`) and
  portal/legal-document downloads (`_get_invoice_legal_documents*`) all go through the
  same ensure path. Send & Print reports a retryable error instead of attaching any
  substitute when the PDF is unavailable, even with the proforma fallback allowed.
- Missing company InvoiceXpress credentials produce a configuration `UserError` before
  any HTTP call.
- Issuance, posting, payment settlement and optional provider email are unchanged;
  nothing is reissued or re-sent.

## Tasks

- [x] Spec the on-demand certified PDF contract.
- [x] Port the connector lookup (`_get_invoice_pdf`) with response-log and redirect
      guards.
- [x] Flag certified PDF attachments on `ir.attachment`.
- [x] Ensure/cache hooks on `account.move` plus report, send-wizard and legal-document
      overrides.
- [x] Regression tests for print, send, portal download, untrusted URLs and native
      documents.
