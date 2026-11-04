Provider-agnostic framework for Portuguese certified legal documents
(sales documents today, transport documents later).

It defines a ``l10n_pt.invoice.provider`` contract plus a
``l10n_pt.invoice.document.mixin`` with the generic document fields
(provider, doc type, provider id, number, permalink) and actions
(create on post, send by email, view document, settle on payment,
block reset to draft).

Provider modules — such as ``l10n_pt_account_invoicexpress`` — implement
the provider contract, their API endpoints and payloads. Journals select
the provider to use; when enabled, posting an invoice automatically
creates the legal document with that provider.
