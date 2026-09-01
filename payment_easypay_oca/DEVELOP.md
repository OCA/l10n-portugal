# EasyPay Odoo Module - Development Guide

## Overview

This module integrates Odoo with EasyPay Checkout — a pre-built payment form that
handles customer information collection, payment method selection, and payment
processing.

**Supported payment methods:** Credit/Debit Cards, MB WAY, Multibanco, SEPA Direct
Debit, Virtual IBAN, Apple Pay, Google Pay, Samsung Pay

**Supported payment types:** Single (one-time), Frequent (tokenization for repeat
charges)

## Architecture

### Core Components

| File                                | Responsibility                                                 |
| ----------------------------------- | -------------------------------------------------------------- |
| `models/payment_provider.py`        | Provider config, EasyPay API calls, payload builders           |
| `models/payment_transaction.py`     | Transaction state machine, token creation, refund/capture/void |
| `controllers/checkout_session.py`   | JSON-RPC: creates EasyPay checkout session on Pay click        |
| `controllers/checkout_page.py`      | Serves the dedicated SDK page (`/payment/easypay/checkout`)    |
| `controllers/webhooks.py`           | Webhook handlers (generic, authorisation, transaction)         |
| `controllers/checkout_callback.py`  | Checkout success/cancel/MB reference page                      |
| `static/src/js/payment_form.esm.js` | Odoo payment form override — initiates session creation        |
| `static/src/js/checkout.js`         | EasyPay SDK initialization and event handlers                  |
| `views/checkout_template.xml`       | Standalone page template hosting the SDK                       |
| `const.py`                          | API URLs, payment method codes, payment type constants         |

---

## Payment Flow

### Step 1 — Transaction creation

**User action:** Selects EasyPay on the Odoo payment page and clicks **Pay Now**.

**Odoo:**

- Creates `payment.transaction` record (state: `draft`)
- Renders the standard Odoo payment form

### Step 2 — Checkout session creation

**Browser (`payment_form.esm.js`):**

- Intercepts `_processRedirectFlow` for `providerCode === "easypay"`
- POSTs to `/payment/easypay/create_checkout_session` (JSON-RPC) with `reference` (the
  Odoo transaction reference)

**Server (`checkout_session.py`):**

- Looks up transaction by reference
- Guard: if `easypay_checkout_id` already set and state is not `draft`, returns
  `{"error": "payment_in_progress", "message": "..."}` — prevents double-session for
  in-flight Multibanco payments
- Calls `_easypay_create_checkout_session()`:
  - `POST https://api.test.easypay.pt/2.0/checkout` (test) or `…api.prod.easypay.pt`
  - Payload includes `type`, `payment.methods`, `order`, `customer`
  - Single payments: adds `payment.type = "sale"` and `payment.capture`
  - Frequent payments: omits those fields (required by EasyPay API)
- Stores `easypay_checkout_id` on transaction
- Returns `{"checkout_manifest": {...}, "checkout_id": "...", "success": true}`

**Browser:**

- Redirects to `/payment/easypay/checkout?session_id=...&manifest=...`

### Step 3 — SDK page

**Server (`checkout_page.py`):**

- Validates `session_id` and `manifest` params
- Looks up transaction by `easypay_checkout_id` to derive `api_url` server-side
- Derives `sdk_language` from `tx.partner_id.lang`: `pt*` → `pt_PT`, `es*` → `es_ES`,
  anything else → `en`
- Serialises `{sessionId, manifest, apiUrl, language}` as `Markup(json.dumps(...))` —
  safe raw JSON injection into the `<script>` block (no HTML-encoding via QWeb)
- Renders `checkout_template.xml` with `window.easyPayData = <json>`

**Browser (`checkout.js`):**

- EasyPay SDK loaded from `https://cdn.easypay.pt/checkout/2.9.1/`
- `window.easypayCheckout.startCheckout(data.manifest, {...})` called
- `testing` flag derived from `data.apiUrl` (true if URL contains "test" or is empty)
- `language` passed from `data.language` (`en`, `pt_PT`, or `es_ES`)
- Payment form rendered inline in `#easypay-checkout` div

### Step 4 — User pays

**Synchronous methods (card):**

- User enters card details
- SDK captures payment, calls `onSuccess` with `payment.status = "paid"` or
  `"authorised"`

**Asynchronous — MB WAY:**

- User enters phone number
- MB WAY push sent to phone; user must confirm on device
- SDK calls `onSuccess` with `payment.status = "pending"` (or `"paid"` if confirmed
  immediately)
- Transaction set to `pending`; later confirmed via webhook → `done`

**Asynchronous — Multibanco:**

- SDK displays an ATM reference to the user
- SDK calls `onSuccess` with `payment.status = "pending"`
- Transaction set to `pending`
- User pays at ATM (may be hours/days later)
- Webhook fires when ATM payment confirmed → transaction → `done`
- ⚠️ If user navigates back and clicks Pay again, the in-progress guard (Step 2) blocks
  a new session and shows: _"A payment is already in progress…"_

**Frequent payment (tokenization):**

- SDK calls `onSuccess` with a `payment.id` (the token reference)
- `onSuccess` passes `payment_id` in the redirect URL
- Server calls `_easypay_create_token(payment_id)` → creates `payment.token` record
- Future charges via `_send_payment_request()` →
  `POST /2.0/capture/{token.provider_ref}`

### Step 5 — SDK event handlers

```javascript
startCheckout(manifest, {
  display: "inline",
  testing: isTestMode,
  onSuccess: function (successInfo) {
    // unmount() then redirect to /checkout/success
  },
  onError: function (error) {
    // unmount() always called first, then:
    // "checkout-expired"  → history.back() (user can retry, new session created)
    // "already-paid"      → /payment/status
    // "checkout-canceled" → /checkout/cancel?session_id=...
    // default             → show error message in #payment-error div
  },
  onPaymentError: function () {
    // Recoverable — SDK keeps form open, user can retry
  },
  onClose: function () {
    // unmount() then /payment/status
    // onClose is NOT a cancellation; transaction remains pending
  },
});
```

> ⚠️ `unmount()` is called before every navigation to prevent SDK memory leaks.

> ⚠️ Sessions expire after **30 minutes**. `checkout-expired` triggers `history.back()`
> so the user can re-click Pay, which creates a fresh session.

### Step 6 — `/checkout/success` handler

**Browser:** redirects to
`/payment/easypay/checkout/success?id={session_id}&method={method}&status={status}`
(optionally `&payment_id={id}` for frequent payments)

**Server (`checkout_callback.py → easypay_checkout_success`):**

1. Finds transaction by `checkout_id` (maps to `easypay_checkout_id`)
2. `GET /2.0/checkout/{easypay_checkout_id}` — fetches authoritative payment data
3. If frequent: calls `tx._easypay_create_token(payment_id)` (idempotent)
4. Calls `tx._handle_notification_data("easypay", payment_data)`
5. `_process_notification_data` resolves status and sets transaction state:
   - `"success"` / `"paid"` / `"captured"` → `done`
   - `"pending"` / `"waiting"` → `pending`
   - `"tokenized"` → `done` (frequent setup complete)
   - Unrecognised status while in `draft` → `pending` (webhook will resolve)
6. Redirects to `/payment/status`

### Step 7 — Webhooks (async confirmation)

EasyPay sends POST notifications to:

- `/payment/easypay/webhook/generic` — flat payload `{id, key, type, status}`
- `/payment/easypay/webhook/authorisation` — flat payload, `status: success` means
  authorised
- `/payment/easypay/webhook/transaction` — nested payload with `transaction` object

**Generic & authorisation webhooks (`webhooks.py → _handle_flat_webhook`):**

1. Resolves EasyPay's event-level `status: "success"` to a concrete payment status:
   - `success` + `capture`/`transaction` event → `"paid"`
   - `success` + `authorisation` event → `"authorised"`
   - Other statuses passed through as-is
2. Extracts `id` (payment ID) and `key` (reference) from body
3. Finds transaction (reference preferred over payment ID)
4. Stores `payment_id` on transaction if not already set
5. `GET` full payment data from EasyPay (checkout or single endpoint)
6. Injects `_resolved_status` into payment data
7. `tx._handle_notification_data(...)` → updates state
8. Always returns HTTP 200 (EasyPay retries on non-200)

**Transaction webhook (`webhooks.py → easypay_transaction_webhook`):**

1. Extracts data from nested `transaction` object
2. Finds transaction, stores `payment_id` if missing
3. Routes by `event_type`:
   - `capture` → fetches payment data, sets `_resolved_status = "paid"`
   - `void` → fetches payment data, sets `_resolved_status = "cancelled"`
   - `refund` → finds the pending refund child tx by `provider_reference`, sets it to
     `done` or `error` based on webhook status
   - Other events → logged and ignored

---

## Status Mapping

| EasyPay status                              | Odoo transaction state     |
| ------------------------------------------- | -------------------------- |
| `pending`, `waiting`                        | `pending`                  |
| `authorized`, `authorised`                  | `authorized`               |
| `captured`, `paid`, `tokenized`, `complete` | `done`                     |
| `cancelled`, `canceled`                     | `cancel`                   |
| `failed`, `error`                           | `error`                    |
| Unrecognised (tx in draft)                  | `pending` (awaits webhook) |

---

## Capture, Refund, Void

### Manual Capture (`_send_capture_request`)

- Requires `provider_reference` (the EasyPay payment ID)
- `POST /2.0/capture/{provider_reference}` with `{descriptive, transaction_key, value}`
- Stores the resulting capture `id` as `easypay_transaction_id`
- Sets transaction → `done`

### Refund (`_send_refund_request`)

- Validates `easypay_transaction_id` exists **before** creating the child tx
- Calls `super()` to create a child refund transaction (standard Odoo pattern via
  `_create_child_transaction`)
- `POST /2.0/refund/{easypay_transaction_id}` with `{value}` (positive amount)
- Stores the refund ID from EasyPay's response as `refund_tx.provider_reference`
- Sets refund tx → `pending`
- **Webhook confirmation:** The transaction webhook fires with `event_type: "refund"`;
  the handler finds the pending refund child tx by `provider_reference` and sets it to
  `done` or `error`

### Void (`_send_void_request`)

- Requires `provider_reference`
- `POST /2.0/authorisation/{provider_reference}/void` (no body)
- Sets transaction → `canceled`

---

## Capture Status After `onSuccess`

| Method            | Immediate? | Status after `onSuccess` | Confirmed by                  |
| ----------------- | ---------- | ------------------------ | ----------------------------- |
| Card              | Yes        | `paid` or `authorised`   | `/checkout/success`           |
| MB WAY            | Sometimes  | `paid` or `pending`      | `/checkout/success` + webhook |
| Multibanco        | No         | `pending`                | Webhook only                  |
| SEPA Direct Debit | No         | `pending`                | Webhook only                  |
| Frequent (setup)  | Yes        | `tokenized`              | `/checkout/success`           |

---

## Data Storage

### Transaction Fields

| Field                     | Description                                     |
| ------------------------- | ----------------------------------------------- |
| `provider_reference`      | EasyPay payment ID (standard Odoo field)        |
| `easypay_transaction_id`  | Capture ID (used for refund and manual capture) |
| `easypay_checkout_id`     | Checkout session ID                             |
| `easypay_payment_method`  | Method selected by user (`cc`, `mb`, `mbw`, …)  |
| `easypay_capture_status`  | Raw capture status from EasyPay                 |
| `easypay_payment_details` | Full JSON response (audit trail)                |
| `token_id`                | Linked `payment.token` (frequent flow only)     |

### Provider Fields

| Field                        | Description                                          |
| ---------------------------- | ---------------------------------------------------- |
| `easypay_account_id`         | EasyPay account identifier                           |
| `easypay_api_key`            | API key (admin-only, encrypted)                      |
| `easypay_payment_method_ids` | Enabled payment methods                              |
| `allow_tokenization`         | `True` — enables the "Save payment details" checkbox |
| `easypay_webhook_base_url`   | Computed — base URL shown in provider form           |

---

## API Endpoints

### EasyPay API

| Endpoint                       | Method | Description                                |
| ------------------------------ | ------ | ------------------------------------------ |
| `/2.0/checkout`                | POST   | Create checkout session                    |
| `/2.0/checkout/{id}`           | GET    | Fetch checkout details                     |
| `/2.0/capture/{id}`            | POST   | Capture frequent payment or manual capture |
| `/2.0/refund/{id}`             | POST   | Process refund (id = capture UUID)         |
| `/2.0/authorisation/{id}/void` | POST   | Void authorised payment                    |
| `/2.0/single/{id}`             | GET    | Fetch single payment details               |
| `/2.0/config`                  | GET    | Read webhook config                        |
| `/2.0/config`                  | PATCH  | Register webhook URLs                      |
| `/2.0/system/ping`             | GET    | Connection test                            |

### Odoo Controllers

| Route                                      | Description                           |
| ------------------------------------------ | ------------------------------------- |
| `/payment/easypay/create_checkout_session` | JSON-RPC: create session on Pay click |
| `/payment/easypay/checkout`                | Serves SDK page                       |
| `/payment/easypay/checkout/success`        | Post-payment redirect (GET)           |
| `/payment/easypay/checkout/cancel`         | SDK-triggered cancel (GET)            |
| `/payment/easypay/mb_reference/<tx_id>`    | Multibanco reference display page     |
| `/payment/easypay/webhook/generic`         | EasyPay generic webhook (POST)        |
| `/payment/easypay/webhook/authorisation`   | EasyPay authorisation webhook (POST)  |
| `/payment/easypay/webhook/transaction`     | EasyPay transaction webhook (POST)    |

---

## Configuration

1. Go to **Accounting → Configuration → Payment Providers**, create or open EasyPay
2. Set **Account ID** and **API Key** (from EasyPay backoffice)
3. Select **Payment Methods** to offer
4. Click **Configure Webhooks** — registers all Odoo webhook URLs with EasyPay
   automatically via `PATCH /2.0/config`
5. Click **Test Connection** to verify credentials

### Payment Method Codes

| Code  | Method            |
| ----- | ----------------- |
| `cc`  | Credit/Debit Card |
| `mb`  | Multibanco        |
| `mbw` | MB WAY            |
| `dd`  | SEPA Direct Debit |
| `vi`  | Virtual IBAN      |
| `ap`  | Apple Pay         |
| `gp`  | Google Pay        |
| `sw`  | Samsung Pay       |

---

## Manual Testing Guide

### Prerequisites

- Provider configured with test credentials (`api.test.easypay.pt`)
- Webhooks registered and reachable (use ngrok or similar if local)
- Provider state set to **Test**

### Test Case 1 — Card payment (checkout flow, immediate)

1. Add an item to cart and proceed to payment
2. Select EasyPay, click **Pay Now**
3. **Expected:** Redirected to `/payment/easypay/checkout` — spinner shown, then SDK
   form appears
4. Select **Credit/Debit Card**, enter test card details
5. **Expected:** `onSuccess` fires, redirected to `/payment/easypay/checkout/success`
6. **Expected:** Odoo transaction state → **Done**
7. **Verify in Odoo:** Transaction has `provider_reference`, `easypay_transaction_id`,
   `easypay_capture_status = "paid"`

### Test Case 2 — MB WAY (async, user confirmation required)

1. Proceed to payment, click **Pay Now**
2. Select **MB WAY**, enter a valid Portuguese mobile number
3. **Expected:** `onSuccess` fires with `status = "pending"` or `"paid"`
4. **Expected:** Redirected to `/checkout/success` → transaction → **Pending** (if
   `"pending"`) or **Done**
5. Confirm (or reject) on the MB WAY app
6. **Expected:** Webhook arrives → transaction → **Done** (or **Error** on rejection)

### Test Case 3 — Multibanco (very async)

1. Proceed to payment, click **Pay Now**
2. Select **Multibanco**
3. **Expected:** SDK displays Entity + Reference + Amount
4. **Expected:** `onSuccess` fires with `status = "pending"`
5. **Expected:** Redirected to `/checkout/success` → transaction → **Pending**
6. Close the browser tab
7. Simulate ATM payment using EasyPay test tools or wait for test webhook
8. **Expected:** Webhook → transaction → **Done**
9. **Retry guard test:** Before paying, go back and click **Pay Now** again
   - **Expected:** Error dialog: _"A payment is already in progress…"_ (no new session
     created)

### Test Case 4 — Session expiry

1. Start checkout, wait 30+ minutes (or simulate via EasyPay test tools)
2. **Expected:** SDK fires `onError` with `error.code = "checkout-expired"`
3. **Expected:** `history.back()` — user returns to payment page
4. Click **Pay Now** again
5. **Expected:** New session created successfully, flow continues normally

### Test Case 5 — Frequent payment setup

1. Configure provider with **Payment Type = Frequent**
2. Proceed to payment, complete card payment
3. **Expected:** `onSuccess` fires with `payment.id`
4. **Expected:** `payment.token` record created in Odoo (visible on transaction)
5. **Verify:** Token has `provider_ref = payment.id`

### Test Case 6 — Frequent payment charge (subsequent)

1. With an existing token from Test Case 5
2. Trigger a new charge via Odoo subscription or manual `_send_payment_request()`
3. **Expected:** `POST /2.0/capture/{token.provider_ref}` called
4. **Expected:** Transaction → **Pending** with `easypay_transaction_id` set
5. **Expected:** Webhook fires → transaction → **Done**

### Test Case 7 — Refund

1. Start from a **Done** transaction
2. Click **Refund** in Odoo
3. **Expected:** `POST /2.0/refund/{easypay_transaction_id}` called
4. **Expected:** Child refund transaction created → state **Pending**
5. **Expected:** Transaction webhook fires with `event_type: "refund"` → refund tx →
   **Done**

---

## Troubleshooting

| Issue                                  | Solution                                                                           |
| -------------------------------------- | ---------------------------------------------------------------------------------- |
| SDK not loading                        | Check CDN availability; `onerror` on the `<script>` tag shows `#payment-error` div |
| `testing` flag mismatch                | Provider state **Test** → `api.test.easypay.pt` → `testing: true` auto-set         |
| `checkout-expired`                     | User hit 30-min limit; `history.back()` lets them restart                          |
| Multibanco not confirmed               | Check webhook delivery; test with ngrok if running locally                         |
| _"Payment already in progress"_        | An earlier Multibanco/MB WAY session is open; pay it or wait for expiry            |
| Payment status stuck on Pending        | Webhook not reachable; check URLs in EasyPay backoffice match Odoo base URL        |
| No `easypay_transaction_id` on Done tx | Webhook payload lacked `capture.id`; refund will fail with validation error        |
| `reference` missing in session         | `processingValues.reference` not passed from JS form                               |
| Refund stuck on Pending                | Transaction webhook not received; check webhook config and delivery                |
