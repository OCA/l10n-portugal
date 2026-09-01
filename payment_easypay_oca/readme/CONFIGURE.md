**Currency requirement:** EasyPay only supports **EUR**. The provider is
pre-configured to appear only for EUR transactions and will be hidden
automatically when the customer's currency is different.

## 1. Create an EasyPay Account

- **Test environment**: Sign up at <https://backoffice.test.easypay.pt/>
- **Production**: Sign up at <https://www.easypay.pt/> and complete merchant
  verification

Once logged in, note your **Account ID** and **API Key** (both UUID format) from
the EasyPay dashboard.

## 2. Configure the Provider in Odoo

1.  Go to **Accounting → Configuration → Payment Providers** (or
    **Website → Configuration → Payment Providers**)
2.  Search for **EasyPay** and open the provider form
3.  Fill in:
    - **Account ID** — from your EasyPay dashboard
    - **API Key** — from your EasyPay dashboard (admin-only field)
    - **Payment Methods** — select the methods to offer (Credit/Debit Card,
      Multibanco, MB WAY, etc.)
    - **Allow Saving Payment Methods** — when enabled, logged-in customers
      can tick "Save my payment details" at checkout to tokenize their
      card or SEPA Direct Debit mandate for future charges
      (e.g. subscriptions). Enabled by default.
4.  Set the provider **State**:
    - **Test Mode** → uses `https://api.test.easypay.pt` and enables the
      `testing` flag in the SDK automatically
    - **Enabled** → uses `https://api.prod.easypay.pt` (production)
5.  Click **Save**

## 3. Register Webhooks

EasyPay sends payment status updates to three separate Odoo endpoints. The
simplest way to register them is to use the built-in button:

1.  On the EasyPay provider form, click **Configure Webhooks**
2.  Odoo will call `PATCH /2.0/config` on the EasyPay API and register:
    - `https://yourdomain.com/payment/easypay/webhook/generic`
    - `https://yourdomain.com/payment/easypay/webhook/authorisation`
    - `https://yourdomain.com/payment/easypay/webhook/transaction`

If you need to register webhooks manually in the EasyPay dashboard, use
the three URLs above. All three must be registered for all payment methods
to work correctly (Multibanco confirmation, for example, arrives via the
transaction webhook).

**Note:** Webhooks must be reachable from the internet. If running locally,
use a tunnel such as localtunnel (https://theboroer.github.io/localtunnel-www/)
or ngrok and update the Odoo base URL accordingly before
clicking **Configure Webhooks**.

## 4. Test the Connection

Click **Test Connection** on the provider form to verify that your
credentials are correct and the EasyPay API is reachable.

## 5. Go Live

1.  Replace test credentials with production values
2.  Change provider **State** to **Enabled**
3.  Click **Configure Webhooks** again to register production webhook URLs
4.  Test with a small real payment before going fully live
5.  Set the provider to **Published** so customers can see it
