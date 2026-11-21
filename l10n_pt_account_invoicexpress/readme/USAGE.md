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


For invoices issued by InvoiceXpress, **Print** and **Send & Print**
use the certified InvoiceXpress PDF. To backfill a missing PDF, open
the posted invoice and choose **Print**. The invoice must retain its
InvoiceXpress document ID, and the company must be configured for the
account that issued it. Odoo fetches and caches the PDF without
reissuing the invoice or sending email.

If the PDF is unavailable, retry later or check the company's
InvoiceXpress credentials. Odoo does not print a substitute.


The monthly SAF-T file should be downloaded from the InvoiceXpress website.
