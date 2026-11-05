Provider-agnostic framework for Portuguese certified **transport
documents** ("Guias de Transporte/Remessa"), mirroring the invoice
framework.

Each `stock.picking.type` can select a legal document provider; when a
delivery of that type is validated, the provider's legal document is
created and its PDF stored on the picking. "View Document" opens the
provider's page or the stored PDF.

Providers implement ``l10n_pt.invoice.provider`` and dispatch on the
document model — e.g. ``l10n_pt_stock_invoicexpress`` handles
transports/shippings/devolutions.
