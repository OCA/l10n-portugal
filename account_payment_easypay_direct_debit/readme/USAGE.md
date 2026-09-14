1. Open customer invoices to collect and use *Add to Payment Order*, or
   create a payment order manually with the EasyPay Direct Debit mode.
   Each payment line must reference a valid EasyPay mandate.
2. **Confirm** the order — draft payments are created (one per
   partner/bank/mandate group).
3. Click **Generate Payment File** — no file is produced for this method;
   the order simply moves to *File Generated*.
4. Click **Mark as Uploaded** — Odoo submits one debit per payment to
   EasyPay and posts/reconciles the payments, exactly as if the file had
   been sent to a bank. If some debits fail, the error lists them and the
   order stays in *File Generated*; fix the cause and retry — already
   submitted debits are not resent.
5. Track results in *Invoicing → Customers → EasyPay Transactions*
   (or from each payment). *Pending* debits are updated automatically by
   EasyPay webhooks and the scheduled polling job.

Rejected or bounced debits are marked *rejected* and an activity is
created on the payment order. The invoice stays marked as paid — reverse
the payment manually (cancel the account payment) as you would for any
failed direct debit.
