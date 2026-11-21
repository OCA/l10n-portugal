## Issue an invoice

1. Open the customer invoice and make sure it uses a sales journal
   configured for InvoiceXpress.
2. Check each product line has exactly one tax. A 0% tax needs its VAT
   exemption reason configured on the tax itself, and all zero-rated
   lines on the invoice must share a single exemption code — split
   invoices that mix different exemption reasons.
3. Confirm the invoice. Odoo posts it, InvoiceXpress issues and numbers
   the legal document, and its number is used on the invoice.
4. Odoo then tries to fetch the certified PDF. If InvoiceXpress is
   still generating it, printing again later simply retries — do not
   repost the invoice.

InvoiceXpress does not accept negative unit prices or quantities. Use
a percentage discount on the affected line instead of a negative
discount line where appropriate.

The invoice form shows an "InvoiceXpress" tab with the provider
document details. **View Document** opens the document page on
InvoiceXpress when a link is available, and otherwise fetches the PDF.

## Print or backfill a certified PDF

To backfill a PDF, open a posted InvoiceXpress invoice migrated from
before Odoo 20 and choose **Print**. The invoice needs its original
InvoiceXpress document ID, and its journal must still point to the
InvoiceXpress account that issued it.

The certified PDF is fetched and cached on demand: printing accepts
only the verified provider document — it never reissues the invoice,
sends email, or falls back to an Odoo layout. There is no dedicated
bulk backfill action. If the PDF is unavailable, retry later or check
the journal's InvoiceXpress credentials.

## Send an invoice

Use the standard **Send & Print** for normal delivery — it mails the
certified InvoiceXpress PDF. If the sales journal has an
**InvoiceXpress Email Template** and the document is issued,
**Email via Provider** is also available; use it instead when you want
InvoiceXpress itself to send the email. Posting never sends email
automatically — pick one path per invoice.

## Credit notes and reporting

Credit notes linked to an InvoiceXpress invoice carry the original
document reference automatically. For a standalone credit note against
an invoice issued outside InvoiceXpress, fill **Reference** with the
full legal series/number (e.g. `FT A/1`) before posting.

If you report these invoices via SAF-T, download the export from
InvoiceXpress.

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
