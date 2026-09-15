## EasyPay account

1. Go to *Invoicing → Configuration → Payment Providers* and open (or
   create) the **EasyPay** provider.
2. Fill in the **Account ID** and **API Key** from your EasyPay backoffice
   and set the provider state (Test = sandbox, Enabled = production).
3. Click **Test Connection** to verify the credentials, then **Configure
   Webhooks** — this registers the Odoo webhook URLs with EasyPay (shared
   by checkout payments and direct debits).
4. Optionally click **Sync Payment Methods**: when your EasyPay account
   has Direct Debit enabled, the `dd` method is activated and becomes
   available at checkout — letting customers grant mandates online that
   can be reused for payment order debits (see *Mandates* below).

## Payment mode

1. Go to *Invoicing → Configuration → Payment Modes* and create a mode:
   - Payment Method: **EasyPay Direct Debit**
   - Payment Type: Inbound
   - EasyPay Provider: the provider configured above
   - Bank Journal: the journal used to book the collected debits
2. Make sure the journal's *Incoming Payments* tab includes the **EasyPay
   Direct Debit** method.

## Mandates

For each customer to debit:

1. Go to *Invoicing → Customers → Mandates* and create a mandate with
   **Format = EasyPay SEPA**, the customer's bank account (IBAN) and the
   signature date. The partner must have an email and phone number —
   EasyPay requires them for mandate registration.
2. Optionally set **EasyPay Token** to reuse an authorization the
   customer already granted through the EasyPay checkout.
3. Click **Validate**: the mandate is registered with EasyPay and the
   EasyPay reference is stored. Validation fails if the API rejects it.
