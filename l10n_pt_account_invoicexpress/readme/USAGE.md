On an Invoice, the CONFIRM button automatically generates an invoice on
the InvoiceXpress service, and downloads its PDF as the invoice's
reference document. The standard Odoo **Send & Print** button sends this
certified PDF by email — Odoo-generated invoice layouts are not used.

The "View Document" button opens the document page on InvoiceXpress.

Use **Send & Print** for normal delivery from Odoo. If the sales journal
has an **InvoiceXpress Email Template**, **Email via Provider** is also
available on the issued invoice. Use that action instead of **Send &
Print** when you want InvoiceXpress to send the email. Posting alone does
not send an email.

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

## Live API test

`TestInvoiceXpressLive` is an opt-in smoke test that performs a real,
read-only `GET taxes.json` request against InvoiceXpress. It carries the
`-standard` tag, so the ordinary test suite never runs it, and it only
executes when all three environment variables are set — take them from
your secret store or shell, never hardcode them:

- `INVOICEXPRESS_ACCOUNT_NAME`
- `INVOICEXPRESS_API_KEY`
- `INVOICEXPRESS_COMPANY_VAT`

`INVOICEXPRESS_COMPANY_VAT` configures the VAT of the local Portuguese
test company; the `GET taxes.json` request does not send it and does not
verify the remote tax identity. If any variable is missing, the test
skips. Run it against a disposable installed Odoo 20 database with:

```
odoo-bin -d <test-database> -u l10n_pt_account_invoicexpress \
    --test-tags invoicexpress_live/l10n_pt_account_invoicexpress \
    --stop-after-init
```
