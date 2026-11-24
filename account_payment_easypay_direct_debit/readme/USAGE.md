1. Open customer invoices to collect and use *Add to Payment Order*, or
   create a payment order manually with the EasyPay Direct Debit mode.
   Each payment line must reference a valid EasyPay mandate.
2. **Confirm** the order — draft payments are created (one per
   partner/bank/mandate group).
3. Click **Generate Payment File** — no file is produced for this method;
   the order moves to *File Generated* and each payment reserves its
   debit: provider, mandate, amount and reference are frozen on a draft
   transaction, but nothing is sent to EasyPay yet.
4. Click **Prepare EasyPay Upload** — this arms the order and starts the
   23-hour submission window. Preparing again keeps the original
   timestamp.
5. Click **Mark as Uploaded** — Odoo submits the reserved debits to
   EasyPay and posts/reconciles the payments, exactly as if the file had
   been sent to a bank. Upload must happen within 23 hours of Prepare;
   a retry reuses the exact same request (same reference and
   idempotency key), so an ambiguous earlier attempt cannot debit twice.
   If the window expired or a reservation is ambiguous, reconcile the
   debit in EasyPay before retrying — the order stays in *File
   Generated* until every debit is submitted. Once the order is prepared
   — or EasyPay has acknowledged any debit — it can no longer be
   cancelled, regenerated or deleted; reconcile the debits in EasyPay
   first.
6. Track results in *Invoicing → Customers → EasyPay Transactions*
   (or from each payment). *Pending* debits are updated automatically by
   EasyPay webhooks and the scheduled polling job.

Rejected or bounced debits are marked *rejected* and an activity is
created on the payment order. The invoice stays marked as paid — reverse
the payment manually (cancel the account payment) as you would for any
failed direct debit.
