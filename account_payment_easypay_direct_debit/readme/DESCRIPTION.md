Collect SEPA Direct Debits from your customers through EasyPay
(https://easypay.pt) using standard OCA payment orders.

Instead of generating a PAIN.008 file to upload to a bank, payment orders
using the *EasyPay Direct Debit* payment mode submit each debit directly to
the EasyPay API when the order is marked as uploaded.

Features:

- Register SEPA mandates with EasyPay directly from the mandate form —
  validation calls the EasyPay API and stores the returned mandate
  reference. A mandate can also reuse an existing EasyPay authorization
  created through the EasyPay checkout (`payment_easypay_oca`).
- Submit direct debits in batch from *Invoicing → Payments → Payment
  Orders* — one EasyPay debit per generated account payment.
- Track each debit in the *EasyPay Transactions* log: pending, paid,
  rejected or error, with the raw API response for debugging.
- Automatic status updates via EasyPay webhooks (shared with
  `payment_easypay_oca`) plus a scheduled polling fallback.
- Rejected debits create an activity on the payment order so the
  accounting team can follow up.

Runs on Odoo Community and Enterprise — it depends only on OCA
`bank-payment` modules and `payment_easypay_oca`, never on Enterprise
batch-payment or SEPA modules.
