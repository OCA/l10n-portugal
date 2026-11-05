Generate Portuguese tax authority legal documents using
`Moloni <https://moloni.pt>`__, on top of the
``l10n_pt_invoice_provider`` framework.

**ALPHA / EXPERIMENTAL** — this module It implements the core
document creation flow (customers, insert + finalize, document
number and PDF retrieval) but has known gaps:

- Payment settlement is not implemented (Moloni uses separate
  Receipt documents).
- Provider-side email is disabled; use Odoo's standard
  Send & Print, which mails the Moloni PDF stored as the invoice's
  reference document.
- Moloni country/payment/delivery method identifiers in the
  customer payload are placeholders (Portugal-only).

Configuration lives on the Company (Moloni API credentials and
Moloni company id) and on each sales Journal (provider selection and
document type). OAuth2 tokens are handled automatically.
