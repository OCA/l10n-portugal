## Set up InvoiceXpress

InvoiceXpress is a paid certified-invoicing service. Before connecting
Odoo, prepare the account using the official
[InvoiceXpress API setup tutorial](https://invoicexpress.com/faqs/api/utilizar/)
(Portuguese):

- In the InvoiceXpress account, verify the company name, address and
  Portuguese NIF match the Odoo company.
- Set up the invoice series following the official
  [series setup guide](https://invoicexpress.com/blog/series-de-faturacao-o-que-sao-e-como-comunicar/)
  and confirm the proper series and defaults for each document type,
  including AT registration where applicable. Odoo does not configure
  or send a series — it uses the account's defaults.
- Confirm the AT communication method with your accountant using the
  [AT communication guide](https://invoicexpress.com/faqs/at/comunicacao-documentos/).
- Generate an API key under **Conta > Integrações > API > Gerar
  chave** in the InvoiceXpress web app.
- Note the account name: it is the subdomain before
  `.app.invoicexpress.com` — do not copy the whole URL. Keep the API
  key private.

## Connect an Odoo sales journal

1. Switch to the Portuguese company that issues the documents.
2. As an accounting administrator, open **Accounting > Configuration**.
   Under **Accounting**, select **Journals** and open the sales journal.
3. Select **InvoiceXpress** in **Legal Document Provider**, then fill in
   **InvoiceXpress Account Name**, **InvoiceXpress API Key** and
   **InvoiceXpress Doc Type** (Invoice, Invoice Receipt or Simplified
   Invoice).
4. Optionally select an **InvoiceXpress Email Template** — the shipped
   `InvoiceXpress: Send Invoice by Email` template can be chosen
   explicitly. Leave it empty to send invoices from Odoo only.

Use a separate journal for each InvoiceXpress account, and do not
change the underlying account of a journal that already issued
invoices. On databases migrated from earlier versions, review that the
journal's account name and API key still point to the original
InvoiceXpress account before printing historical documents.

## Before going live

- Test posting from a disposable Odoo database connected to an
  InvoiceXpress sandbox, not a production account.
- Verify the remote document number and that **Print** shows the
  certified InvoiceXpress PDF.
- Decide the email path: standard Odoo **Send & Print** or the optional
  **Email via Provider** action.
