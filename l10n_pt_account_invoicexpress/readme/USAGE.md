On an Invoice, the CONFIRM button automatically generates an invoice on
the InvoiceXpress service, and downloads its PDF as the invoice's
reference document. The standard Odoo **Send & Print** button sends this
certified PDF by email — Odoo-generated invoice layouts are not used.

The "View Document" button opens the document page on InvoiceXpress, and
the "Email via Provider" button asks the InvoiceXpress service to send
the email itself (requires the InvoiceXpress email template).

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
- Each invoice line must have exactly one tax configured;
  InvoiceXpress accepts a single tax per item.
- A 0% tax needs a VAT exemption reason configured on the tax
  itself; the reason is sent once for the whole document.
- Invoices whose lines use different exemption reasons are rejected
  before sending — split them into one invoice per reason.


The monthly SAF-T file should be downloaded from the InvoiceXpress website.
