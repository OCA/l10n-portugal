**Using the invoice form**

1. Create a customer invoice or credit note in a sales journal with a
   configured provider. Review the document type before confirming.
   The type is editable while the document is in draft.
2. Confirm the document. Odoo asks the provider to issue it when the
   invoice actually posts, not when an invoice is scheduled. Once the
   invoice is linked to a legal document, it cannot be reset to draft.
3. Use **View Document** to open the provider link. When there is no
   link, Odoo opens the stored PDF if one is available. When the
   provider returns a PDF, Odoo stores it as the invoice's reference
   document for the standard **Send & Print** flow.
4. Use **Email via Provider** if you want the provider to send the
   email. The button is available for an issued document when the
   provider supports email and is configured for it. For providers
   that track payment status, Odoo asks them to settle the document
   when the invoice becomes fully paid.

For posted invoices issued through a provider, Odoo uses the provider's
PDF for printing and sending. If the PDF is not available, try again
later; Odoo does not generate a substitute. Posted customer invoices
on Portuguese journals without a provider print as proforma invoices.

**Implementing a provider**

Add `l10n_pt_invoice_provider` to your addon's dependencies. Define
an Odoo model inheriting `l10n_pt.invoice.provider`, give it its own
`_name` and `_description`, and set a unique `_provider_code`. Register
the provider so the journal selector can offer it — typically from the
addon's `post_init_hook`:

```python
def post_init_hook(env):
    env["l10n_pt.invoice.provider.record"]._register_provider("my_code")
```

Registration creates a durable `l10n_pt.invoice.provider.record` row
named after the model's description. The journal selector lists only
records whose adapter is currently installed. Provider records survive
adapter uninstallation: issued documents keep their provider link and
cached PDFs remain printable, while posting a new document for a
removed provider is blocked until the adapter is reinstalled.

Implement the provider contract:

- `is_available(journal)`: check the company and journal configuration
  needed to issue documents.
- `get_document_type(document)`: return the provider's document type
  code for the record.
- `prepare_document_vals(document)`: build the provider-specific API
  payload. Call this from your `create_document` implementation as
  needed; the framework calls `create_document` directly.
- `create_document(document)`: create and finalize the legal document.
  Store the results in `l10n_pt_doc_id`, `l10n_pt_doc_number` and
  `l10n_pt_doc_permalink` when available.

Optional methods cover numbering (`get_doc_prefix(doc_type)`), PDF
retrieval (`get_document_pdf(document)`, returning bytes or `None`),
settlement (`settle_document(document)`), and provider-side email
(`can_email_document(journal)` and
`email_document(document, ignore_no_config=False)`). Only advertise
email support if you implement sending and the journal is configured
for it.

`account.move` already uses `l10n_pt.invoice.document.mixin`. The
mixin supplies the `l10n_pt_doc_*` fields and the document actions:
`l10n_pt_create_document()`, `action_l10n_pt_view_document()` and
`action_l10n_pt_send_email()`. The sales posting flow calls the creation
action for eligible moves without a provider document ID; provider
addons should not create a second document from their own posting hook.
