Once configured, customers can use EasyPay to make payments:

1.  During checkout, select **EasyPay** as the payment method
2.  Click **Pay Now**
3.  A secure inline payment form loads. The customer selects a payment
    method and completes the payment without leaving the site.

## Payment method behaviour

- **Credit/Debit Card**: Payment is captured immediately. Order is
  confirmed as soon as the card is charged.
- **MB WAY**: The customer enters their mobile number. A push
  notification is sent to their phone for confirmation. The order is
  placed in *Pending* state until the user confirms (or rejects) on
  the MB WAY app.
- **Multibanco**: An ATM reference (Entity + Reference + Amount) is
  displayed. The customer pays at any ATM or via online banking. The
  order remains *Pending* until the payment is confirmed, which may
  take minutes to days. The customer should **not** close the
  confirmation page before noting down the reference.
- **SEPA Direct Debit**: The customer enters their IBAN and accepts a
  SEPA mandate authorizing EasyPay to debit their account. The order
  remains *Pending* until the bank settles the debit (typically 2–5
  business days). When used with tokenization, the mandate is saved
  and subsequent charges are pulled automatically.
- **Virtual IBAN**: A dedicated IBAN is displayed. The customer
  transfers the exact amount via online banking. The order remains
  *Pending* until the transfer is received and matched by EasyPay.
- **Save payment details (tokenization)**: Logged-in customers can
  tick *Save my payment details* at checkout. The payment method is
  saved as a token for future charges (e.g. subscriptions). This
  works with cards and SEPA Direct Debit.

## Refunds

Refunds can be initiated from the Odoo backend on any confirmed
transaction:

1. Open the payment transaction and click **Refund**
2. A refund request is sent to EasyPay and a child refund transaction
   is created in *Pending* state
3. Once EasyPay processes the refund, a webhook updates the refund
   transaction to *Done* (or *Error* if it failed)

Partial refunds are supported — enter the amount to refund when
prompted.

## Test card details (test environment only)

See the [EasyPay Payment Methods guide](https://docs.easypay.pt/docs/guides/payment-methods)
for full test credentials for all payment methods.
