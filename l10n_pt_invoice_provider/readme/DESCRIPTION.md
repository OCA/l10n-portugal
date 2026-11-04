Provider-agnostic framework for Portuguese certified legal documents
(sales documents today, transport documents later).

It defines a ``l10n_pt.invoice.provider`` contract plus a
``l10n_pt.invoice.document.mixin`` with the generic document fields
(provider, doc type, provider id, number, permalink) and actions.

Provider modules — such as ``l10n_pt_account_invoicexpress`` — implement
the provider contract, their API endpoints and payloads.

User interface
--------------

- **Journal provider selection** — each sales journal picks the legal
  document provider to use (or none); providers can validate
  journal-scoped configuration.
- **Automatic document on post** — posting an invoice creates and
  finalizes the legal document on the provider; scheduled invoices are
  left alone until they actually post.
- **Legal PDF as the reference document** — the provider's PDF is
  downloaded and stored as the invoice's official report, so the
  standard **Send & Print** button mails the certified document.
  *View Document* opens the provider's public page, falling back to
  the stored PDF when the provider has no public link.
- **Email via Provider** — shown only for providers that support and
  are configured for provider-side sending.
- **Settle on payment** — paying the invoice marks the provider
  document settled (for providers that track it).
- **Draft protection** — invoices linked to a legal document cannot be
  reset to draft, in the UI and through RPC.
