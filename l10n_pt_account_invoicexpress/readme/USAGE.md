On an Invoice, the CONFIRM button automatically generates an invoice on
the InvoiceXpress service.

The "Email InvoiceXpress" button requests the InvoiceXpress service to
send an email with a copy of the legal document.

The Invoice form shows an "InvoiceXpress" tab containing details for the
corresponding InvoiceXpress document.

Invoices:

- Added support to the different documents types: Invoice, Invoice
  Receipt, Simplified Invoice. The default document type is set on the
  Journal, and can be changed on the Invoice form.
- Use the invoice commercial partner for the name and address, instead
  of the invoice contact.
- Added support for the Terms and Conditions/Observations field
- Added to Credit Notes the link to the source Invoice
- For standalone credit notes (invoices created outside InvoiceXpress), fill the Reference field with the invoice series/number (e.g., "FT A/1") before posting
- Debit Notes created with Odoo's Debit Note action on a posted invoice
  are issued by InvoiceXpress as ND documents linked to the original
  invoice. If InvoiceXpress issued the original, use the same account.
  For originals issued elsewhere, Odoo sends the original document number.


The monthly SAF-T file should be downloaded from the InvoiceXpress website.
