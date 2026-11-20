Generate Portuguese tax authority legal Invoices ("Faturas") using
InvoiceXpress.


InvoiceXpress is a paid service. Visit <https://invoicexpress.com> for
more details.

Once the InvoiceXpress connection is configured, the invoice CONFIRM
button automatically generates the InvoiceXpress invoice.

If the InvoiceXpress Invoice email template is configured, the
InvoiceXpress service will also send the invoice by email, using the
details in Odoo configured email template.

The generated InvoiceXpress PDF is stored as the invoice's reference
document, so the standard Odoo SEND & PRINT button mails the certified
document — other print layouts are not allowed by the Portuguese Tax
Authority.

Legal transport documents ("Guias de Transporte" e "Guias de Remessa)
are also supported through an extension module. For this please ensure that
"l10n_pt_stock_invoicexpress" is installed.
