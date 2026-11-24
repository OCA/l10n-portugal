## EasyPay account

1. Go to *Invoicing → Configuration → Payment Providers* and open (or
   create) the **EasyPay** provider.
2. Fill in the **Account ID** and **API Key** from your EasyPay backoffice
   and set the provider state (Test = sandbox, Enabled = production).
3. Click **Test Connection** to verify the credentials, then **Configure
   Webhooks** — this registers the Odoo webhook URLs with EasyPay (shared
   by checkout payments and direct debits).

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
2. Optionally set **EasyPay Token** to reuse an externally provisioned
   EasyPay authorization — it must belong to the same customer, provider
   and bank account (IBAN), and validation checks the remote mandate
   before reusing it. Token-based mandates do not need preparation.
3. For a standalone registration, click **Prepare EasyPay Registration**
   first: it freezes the provider and mandate data without contacting
   EasyPay and starts a 23-hour window — preparing again with unchanged
   data is a no-op. If the prepared inputs later change, the mandate must
   be recreated.
4. Click **Validate** within the window: the mandate is registered with
   EasyPay and the EasyPay reference is stored. Validation fails if the
   API rejects it, if the window expired, or if the mandate was not
   prepared. When the original response was lost, an administrator can
   fill in **EasyPay Registration Recovery ID** (visible to administrators
   only) with the frequent payment ID shown in the EasyPay backoffice —
   validation then adopts it after verifying the key, IBAN and status
   instead of posting again.
