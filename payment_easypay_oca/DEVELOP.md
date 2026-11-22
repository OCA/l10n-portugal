# EasyPay Odoo Module - Development Guide

## Overview

This module integrates Odoo with EasyPay Checkout — a pre-built payment form that
handles customer information collection, payment method selection, and payment
processing.

**Supported payment methods:** Credit/Debit Cards, MB WAY, Multibanco, Virtual IBAN,
Apple Pay, Google Pay, Samsung Pay

> SEPA Direct Debit (`dd`) is reserved for a future implementation: the
> `payment_method_easypay_direct_debit` record exists but is inactive — it is not linked
> to the provider, not a default method, and the sync action only deactivates
> module-owned methods it doesn't return.

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
  Odoo transaction reference) and `access_token` (injected into `processingValues` by
  `_get_specific_processing_values`)

**Server (`checkout_session.py`):**

- Looks up transaction by reference and verifies `access_token` — a domain-separated
  HMAC capability minted by `_easypay_checkout_access_token()` and compared with
  `consteq` — prevents session creation for arbitrary/guessable references
- At most one checkout per transaction: the row is locked (`SELECT … FOR UPDATE`) before
  the guard so concurrent session requests serialize. A draft transaction whose stored
  checkout matches this browser session's manifest is reused — a retry can never start a
  second payable session. Any other existing checkout or non-draft state returns
  `{"error": "payment_in_progress", "message": "..."}`; a stored checkout is never
  replaced because its payment may still settle
- Calls `_easypay_create_checkout_session()`:
  - `POST https://api.test.easypay.pt/2.0/checkout` (test) or `…api.prod.easypay.pt`
    with a deterministic `Idempotency-Key` (`_easypay_operation_key("checkout")`) so an
    uncertain response can be retried safely
  - Payload includes `type`, `payment.methods`, `order`, `customer`
  - Single payments: adds `payment.type = "sale"` and `payment.capture`; a Multibanco
    method also adds `payment.multibanco.expiration_time` (RFC3339, from
    `easypay_mb_expiration_days`, default 3) and `payment.multibanco.product` (from
    `easypay_mb_product`, default `CHECKDIGIT`). The API docs ambiguously duplicate the
    nested `multibanco` properties including `product`; that sibling placement still
    needs live verification.
  - Frequent payments: omits those fields (required by EasyPay API) and sends
    `payment.key` = the Odoo transaction reference — the documented merchant payment
    key, distinct from `order.key`
- Stores `easypay_checkout_id` on transaction
- Returns `{"checkout_id": "...", "success": true}` — the manifest stays server-side in
  the browser session only

**Browser:**

- Redirects to `/payment/easypay/checkout?session_id=...`. The browser carries only the
  checkout ID in the page URL. Odoo stores the SDK manifest in the browser session and
  renders it in an escaped data attribute with a CSRF token.

### Step 3 — SDK page

**Server (`checkout_page.py`):**

- Requires `session_id` to match the checkout id stored server-side in this browser
  session; a client-supplied manifest in the query string is never trusted
- Looks up transaction by `easypay_checkout_id` to derive `api_url` server-side
- Derives `sdk_language` from `tx.partner_id.lang`: `pt*` → `pt_PT`, `es*` → `es_ES`,
  anything else → `en`
- Serialises `{sessionId, csrfToken, manifest, apiUrl, language, hideDetails}` as JSON
  and renders it into an escaped `data-easypay` attribute — never inside a `<script>`
  block and never as `window.easyPayData`

**Browser (`checkout.js`):**

- Reads the JSON payload from the `#easypay-checkout` `data-easypay` attribute
- EasyPay SDK loaded from `https://cdn.easypay.pt/checkout/2.9.1/`
- `window.easypayCheckout.startCheckout(data.manifest, {...})` called
- `testing` flag derived from `data.apiUrl` (true if URL contains "test" or is empty)
- `language` passed from `data.language` (`en`, `pt_PT`, or `es_ES`)
- Payment form rendered inline in `#easypay-checkout` div

### Step 4 — User pays

**Synchronous methods (card):**

- User enters card details
- SDK captures payment and calls `onSuccess`; whatever status the SDK reports is only a
  hint — the success route re-reads the payment from EasyPay before any state change

**Asynchronous — MB WAY:**

- User enters phone number
- MB WAY push sent to phone; user must confirm on device
- SDK calls `onSuccess` once the SDK-side flow ends
- Transaction stays `pending` until the authenticated payment read or a webhook confirms
  → `done`

**Asynchronous — Multibanco:**

- SDK displays an ATM reference to the user
- SDK calls `onSuccess`; the authenticated payment read supplies the entity, reference
  and expiration stored on the transaction
- Transaction set to `pending`
- User pays at ATM (may be hours/days later)
- Webhook fires when ATM payment confirmed → transaction → `done`
- ⚠️ If user navigates back and clicks Pay again, the same browser session reuses the
  draft checkout; any other session is blocked by the Step 2 guard and shown _"A payment
  is already in progress…"_

**Frequent payment (tokenization):**

- The SDK success callback carries no payment evidence — only the session id
- On the success route, verified checkout + frequent reads with an active method create
  the `payment.token` and capture the initial amount if nonzero
- Future charges via `_send_payment_request()` →
  `POST /2.0/capture/{token.provider_ref}`

### Step 5 — SDK event handlers

```javascript
startCheckout(manifest, {
  display: "inline",
  testing: isTestMode,
  language: data.language,
  hideDetails: data.hideDetails,
  onSuccess: function () {
    // unmount() then POST {csrf_token, session_id} to /checkout/success
  },
  onError: function (error) {
    // unmount() always called first, then:
    // "checkout-expired"  → history.back() (user can retry, new session created)
    // "already-paid"      → /payment/status
    // "checkout-canceled" → POST {csrf_token, session_id} to /checkout/cancel
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

The SDK posts the checkout ID and CSRF token to the success or cancel route. The success
route requires the checkout to belong to the current browser session. The cancel route
is read-only: browser abandonment is not an EasyPay payment cancellation, so it never
changes the transaction — only EasyPay can confirm one.

> ⚠️ `unmount()` is called before every navigation to prevent SDK memory leaks.

> ⚠️ Sessions expire after **30 minutes**. `checkout-expired` triggers `history.back()`
> so the user can re-click Pay, which creates a fresh session.

### Step 6 — `/checkout/success` handler

**Browser:** POSTs `csrf_token` + `session_id` (the opaque checkout ID) to
`/payment/easypay/checkout/success`

The success callback reads checkout, payment and capture data from EasyPay before
updating Odoo. For Multibanco, the entity and reference come from the authenticated
payment read. For a completed frequent checkout with an active method, Odoo creates the
payment token and captures the initial amount if nonzero.

**Server (`checkout_callback.py → easypay_checkout_success`):**

1. Requires `session_id` to match the checkout stored in this browser session — never a
   payment id or transaction reference
2. `GET /2.0/checkout/{easypay_checkout_id}` — fetches authoritative checkout data
3. `GET /2.0/single/{id}` or `GET /2.0/frequent/{id}` — fetches payment details (method,
   captures, Multibanco entity/reference)
4. Verified frequent checkout → token + initial capture; verified Multibanco → stores
   entity/reference and redirects to the protected reference page
5. Otherwise resolves the capture notification from the verified reads and calls
   `tx._handle_notification_data("easypay", notification)`
6. Redirects to `/payment/status`

### Step 7 — Webhooks (async confirmation)

EasyPay sends POST notifications to:

- `/payment/easypay/webhook/generic` — flat payload `{id, key, type, status}`
- `/payment/easypay/webhook/authorisation` — flat payload, `status: success` means
  authorised
- `/payment/easypay/webhook/transaction` — nested payload with `transaction` object

Webhooks use the event only to locate the payment and decide what to read back. They
apply authenticated results only, acknowledging unknown or conflicting resources without
updating Odoo. Unavailable or inconclusive reads return 503. A late authorisation cannot
replace a submitted capture.

**Dispatch (`webhooks.py → _handle_webhook`):**

- `type: "void"` → `_process_void_event`: matches the locally stored `easypay_void_id`,
  reads `GET /2.0/void/{id}` and applies the outcome
- `type: "refund"` → `_process_refund_event`: matches the pending refund child tx by
  `provider_reference`, reads `GET /2.0/refund/{id}` and sets it `done`/`error`
- `type: "authorisation"` → `_process_authorisation_event`: reads the checkout and
  `GET /2.0/authorisation/{payment_id}`; skipped entirely once a capture id is stored
- `type: "frequent_create"` → `_process_frequent_create_event`: completes a tokenized
  frequent checkout whose browser callback never ran, through the same verified
  checkout + frequent reads as the success route; the event's key and payment id are
  untrusted hints only
- capture/payment events → `_process_payment_event`: resolves exactly one capture via
  `GET /2.0/capture/{id}` or falls back to the payment-level status from
  `GET /2.0/checkout/{id}`, `GET /2.0/single/{id}` or `GET /2.0/frequent/{id}`

Every state change goes through `_handle_notification_data` with data verified against
the stored checkout id, payment id, currency and amount.

**Retries and uncertain submissions:** EasyPay honours `Idempotency-Key` on POST for
24h. Checkout, capture and void requests carry deterministic keys derived from the
transaction (`_easypay_operation_key`); transport failures raise
`const.EasyPayTransportError` so the request rolls back and the same key is retried,
while definitive API rejections remain plain `ValidationError`s.

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

- Row-locks the transaction, then no-ops unless the state is `authorized` with no stored
  capture — a repeated capture click cannot submit twice
- Rejected while a void outcome is unknown (`easypay_void_id` set)
- Requires `provider_reference` (the EasyPay payment ID)
- `POST /2.0/capture/{provider_reference}` with `{descriptive, transaction_key, value}`
  and a deterministic `Idempotency-Key` (`_easypay_operation_key("capture")`)
- Stores the resulting capture `id` as `easypay_transaction_id`

A capture acknowledgement is not settlement: Odoo polls `GET /2.0/capture/{id}` and
applies the outcome only when the read verifies the capture id, merchant reference,
amount and payment binding (`_easypay_verify_capture`); the mapped status is stored in
`easypay_capture_status`. Unresolved captures stay pending for webhook confirmation.

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

- Row-locks the transaction, then no-ops unless the state is `authorized` with no stored
  capture
- Requires `provider_reference`
- POST /2.0/void/{provider_reference} queues the void with a deterministic
  `Idempotency-Key` (`_easypay_operation_key("void", easypay_void_attempt)`). Odoo
  stores the returned void ID and blocks capture while the outcome is unknown. A
  matching webhook or a repeat click on Void checks GET /2.0/void/{id}; only verified
  success cancels, and only a verified failure releases the guard — which also
  increments `easypay_void_attempt` so the next attempt uses a fresh key.

---

## Capture Status After `onSuccess`

| Method           | Immediate? | Status after `onSuccess` | Confirmed by                  |
| ---------------- | ---------- | ------------------------ | ----------------------------- |
| Card             | Yes        | `paid` or `authorised`   | `/checkout/success`           |
| MB WAY           | Sometimes  | `paid` or `pending`      | `/checkout/success` + webhook |
| Multibanco       | No         | `pending`                | Webhook only                  |
| Frequent (setup) | Yes        | `tokenized`              | `/checkout/success`           |

---

## Data Storage

### Transaction Fields

| Field                     | Description                                             |
| ------------------------- | ------------------------------------------------------- |
| `provider_reference`      | EasyPay payment ID (standard Odoo field)                |
| `easypay_transaction_id`  | Capture ID (used for refund and manual capture)         |
| `easypay_checkout_id`     | Checkout session ID                                     |
| `easypay_payment_method`  | Method selected by user (`cc`, `mb`, `mbw`, …)          |
| `easypay_capture_status`  | Normalized EasyPay capture status                       |
| `easypay_mb_entity`       | Multibanco entity (authenticated read only)             |
| `easypay_mb_reference`    | Multibanco reference (authenticated read only)          |
| `easypay_mb_expiration`   | Multibanco reference expiration                         |
| `easypay_void_id`         | Void operation ID (blocks capture until resolved)       |
| `easypay_void_attempt`    | Verified failed void attempts (keys the next void POST) |
| `easypay_payment_details` | Full JSON response (audit trail)                        |
| `token_id`                | Linked `payment.token` (frequent flow only)             |

`provider_reference` normally holds the EasyPay payment id, but legacy rows may store
the checkout id there — or, for token-backed offline transactions, the capture UUID.
`_easypay_payment_reference()` is the single contract for "the EasyPay payment id": it
rejects checkout/capture-id impostors and falls back to `token_id.provider_ref`. A
token-backed capture can use this fallback. For standalone mandates without an Odoo
token, PR #185 must store the mandate's frequent payment ID as provider_reference (or
override this helper); `easypay_transaction_id` stores the capture ID.

### Provider Fields

| Field                      | Description                                          |
| -------------------------- | ---------------------------------------------------- |
| `easypay_account_id`       | EasyPay account identifier                           |
| `easypay_api_key`          | API key (admin-only, encrypted)                      |
| `payment_method_ids`       | Enabled payment methods (standard m2m)               |
| `allow_tokenization`       | `True` — enables the "Save payment details" checkbox |
| `easypay_webhook_base_url` | Computed — base URL shown in provider form           |

---

## API Endpoints

### EasyPay API

| Endpoint                  | Method | Description                                |
| ------------------------- | ------ | ------------------------------------------ |
| `/2.0/checkout`           | POST   | Create checkout session                    |
| `/2.0/checkout/{id}`      | GET    | Fetch checkout details                     |
| `/2.0/capture/{id}`       | POST   | Capture frequent payment or manual capture |
| `/2.0/capture/{id}`       | GET    | Poll capture status                        |
| `/2.0/refund/{id}`        | POST   | Process refund (id = capture UUID)         |
| `/2.0/refund/{id}`        | GET    | Read refund status                         |
| `/2.0/void/{payment_id}`  | POST   | Queue void of an authorised payment        |
| `/2.0/void/{void_id}`     | GET    | Read void status                           |
| `/2.0/single/{id}`        | GET    | Fetch single payment details               |
| `/2.0/frequent/{id}`      | GET    | Fetch frequent payment details             |
| `/2.0/authorisation/{id}` | GET    | Read authorisation status                  |
| `/2.0/config`             | GET    | Read webhook config                        |
| `/2.0/config`             | PATCH  | Register webhook URLs                      |
| `/2.0/system/ping`        | GET    | Connection test                            |

### Odoo Controllers

| Route                                      | Description                                                       |
| ------------------------------------------ | ----------------------------------------------------------------- |
| `/payment/easypay/create_checkout_session` | JSON-RPC: create session on Pay click (requires `access_token`)   |
| `/payment/easypay/checkout`                | Serves SDK page (session-bound manifest + CSRF token)             |
| `/payment/easypay/checkout/success`        | SDK success callback (POST + CSRF, `session_id` only)             |
| `/payment/easypay/checkout/cancel`         | SDK cancel callback (POST + CSRF; read-only, never changes state) |
| `/payment/easypay/mb_reference/<tx_id>`    | Multibanco reference display page (scoped access token)           |
| `/payment/easypay/webhook/generic`         | EasyPay generic webhook (POST)                                    |
| `/payment/easypay/webhook/authorisation`   | EasyPay authorisation webhook (POST)                              |
| `/payment/easypay/webhook/transaction`     | EasyPay transaction webhook (POST)                                |

---

## Configuration

1. Go to **Accounting → Configuration → Payment Providers**, create or open EasyPay
2. Set **Account ID** and **API Key** (from EasyPay backoffice)
3. Select **Payment Methods** to offer
4. Click **Configure Webhooks** — registers all Odoo webhook URLs with EasyPay
   automatically via `PATCH /2.0/config`
5. Click **Test Connection** to verify credentials

### Payment Method Codes

| Code  | Method                                            |
| ----- | ------------------------------------------------- |
| `cc`  | Credit/Debit Card                                 |
| `mb`  | Multibanco                                        |
| `mbw` | MB WAY                                            |
| `dd`  | SEPA Direct Debit — reserved, not yet implemented |
| `vi`  | Virtual IBAN                                      |
| `ap`  | Apple Pay                                         |
| `gp`  | Google Pay                                        |
| `sw`  | Samsung Pay                                       |

---

## Running Local Tests

Run from an Odoo 18 `osh` workspace with this checkout on the addons path. Set `TEST_DB`
to a dedicated test database, not a development or production database. If the module is
not installed there, install it once without enabling tests:

```bash
TEST_DB=easypay-test
osh odoo -d "$TEST_DB" -i payment_easypay_oca --stop
```

Run the standard mocked suite without credentials, a tunnel, or network access to
EasyPay:

```bash
osh odoo -d "$TEST_DB" -u payment_easypay_oca \
  --test-tags /payment_easypay_oca --stop
```

If another Odoo process is already running, choose a free port with `--http-port`.

### Live sandbox tests

The live tests are excluded from the standard suite. They require the explicit
`easypay_live` tag and both `EASYPAY_TEST_ACCOUNT_ID` and `EASYPAY_TEST_API_KEY`. If
either credential is missing, the suite skips before making a request. It only uses the
EasyPay sandbox (`api.test.easypay.pt`). No public tunnel is needed.

Use a local secret store to set the environment variables. For example, with single-line
entries in `pass`, use a subshell so the exports do not persist:

```bash
(
  set +x
  unset EASYPAY_TEST_ALLOW_WRITES
  EASYPAY_TEST_ACCOUNT_ID="$(pass show easypay/sandbox/account-id)" &&
  EASYPAY_TEST_API_KEY="$(pass show easypay/sandbox/api-key)" &&
  export EASYPAY_TEST_ACCOUNT_ID EASYPAY_TEST_API_KEY &&
  osh odoo -d "$TEST_DB" -u payment_easypay_oca \
    --test-tags easypay_live/payment_easypay_oca --stop
)
```

Never commit credentials or enable HTTP/SQL debug logging with credentials loaded. The
command above only runs Odoo's Test Connection action (GET `/2.0/system/ping` and GET
`/2.0/config`). To also run the Multibanco checkout smoke test, prefix the `osh` command
inside the subshell with `EASYPAY_TEST_ALLOW_WRITES=1`. This creates one unsubmitted
checkout that stays in the sandbox; it does not run the SDK, verify the reference
expiry, settle a payment, or exercise webhook delivery.

### Verify webhook registration

Webhook registration is a separate, opt-in sandbox test of the provider's **Configure
Webhooks** action. Use a dedicated sandbox account with `config:read` and
`config:update` scopes and a verified public HTTPS webhook-only endpoint as described
below. Save the current three notification URLs from the sandbox backoffice before
running the test.

By default the test expects the payment account UUID to equal the API Account ID. If the
backoffice shows a separate beneficiary/payment account UUID for these credentials, set
`EASYPAY_TEST_CONFIG_ACCOUNT_UUID` to that independently verified value. Do not copy an
unexpected UUID from the API response itself. Both the update and restoration check the
expected payment account before proceeding.

Inside the secret-loading subshell above, replace the `osh` invocation with:

```bash
EASYPAY_TEST_ALLOW_WRITES=1 \
EASYPAY_TEST_WEBHOOK_BASE_URL=https://your-node.your-tailnet.ts.net \
osh odoo -d "$TEST_DB" -u payment_easypay_oca \
  --test-tags easypay_live/payment_easypay_oca:TestEasyPaySandboxWebhooks.test_sandbox_configures_webhooks \
  --stop
```

The test temporarily replaces the account's three notification URLs, checks them via GET
`/2.0/config`, and restores the previous URLs during cleanup. It stops before writing if
the account UUID does not match or any original URL is missing. Do not run it alongside
another webhook configuration change. If the process is interrupted or cleanup fails,
restore the saved URLs manually. This verifies registration, not webhook delivery, and
does not create a payment.

### Run the Multibanco end-to-end check

The [sandbox runner](tests/run_multibanco_sandbox.py) automates reference issuance and
settlement checks. Use the loopback Odoo server and webhook-only proxy below, and run
Odoo with `--max-cron-threads=0` so the transaction cannot settle via a scheduled job.
Use a dedicated database ending in `-test` and a sandbox account that no one else is
testing against. The provider must be published in **Test** mode with Multibanco enabled
and a seven-day expiry. Use an English (US) synthetic customer in Portugal with a test
email and phone number so the SDK can prefill the contact form. Keep EUR active.

Install Playwright and its Chromium browser in the `osh` environment, outside any
production environment. With a local venv runtime:

```bash
osh exec python -m pip install playwright
osh exec python -m playwright install chromium
```

Run from the Odoo workspace. Use the provider and synthetic customer's record IDs from
your isolated database and substitute the actual proxy-only HTTPS origin:

```bash
(
  set +x
  EASYPAY_TEST_ACCOUNT_ID="$(pass show easypay/sandbox/account-id)" &&
  EASYPAY_TEST_API_KEY="$(pass show easypay/sandbox/api-key)" &&
  EASYPAY_TEST_CONFIG_ACCOUNT_UUID="$(pass show easypay/sandbox/config-account-uuid)" &&
  export EASYPAY_TEST_ACCOUNT_ID EASYPAY_TEST_API_KEY EASYPAY_TEST_CONFIG_ACCOUNT_UUID &&
  export EASYPAY_TEST_ALLOW_WRITES=1 &&
  export EASYPAY_TEST_E2E_DB=easypay-test &&
  export EASYPAY_TEST_PROVIDER_ID=1 EASYPAY_TEST_PARTNER_ID=55 &&
  export EASYPAY_TEST_WEBHOOK_BASE_URL=https://your-node.your-tailnet.ts.net &&
  osh odoo shell --no-http --limit-memory-hard=0 -d "$EASYPAY_TEST_E2E_DB" \
    < /path/to/payment_easypay_oca/tests/run_multibanco_sandbox.py
)
```

The shell-only memory override lets Chromium reserve its virtual address space. Leave
the running Odoo server's memory limit unchanged. The loopback server defaults to port
`8177`; override it with `EASYPAY_TEST_ODOO_PORT`. The runner prints a fresh numeric
reference when the checkout is ready. Enter it at
[EasyPay Test Payments](https://backoffice.test.easypay.pt/developers/payments) within
five minutes. Do not pay the reference via a bank. The browser is already closed by this
point, and the runner waits for the matching payment and capture to settle in EasyPay
and for Odoo to move from **Pending** to **Done**. If it times out, check **Developers >
Notifications API 2.0** in the sandbox backoffice.

The runner saves the original three URLs in a private local JSON file before changing
them and verifies restoration on exit, including Ctrl+C. If the process is forcibly
killed or the settings change concurrently, use that backup to check and restore them
manually. The remote checkout remains in the sandbox.

## Manual Testing Guide

Use a dedicated Odoo test database and configure the provider in **Test** mode with
sandbox credentials. A real webhook delivery test needs a public HTTPS URL.

### Expose only webhook routes with Tailscale Funnel

[Tailscale Funnel](https://tailscale.com/docs/features/tailscale-funnel) is public;
Tailscale Serve is private to the tailnet and won't receive EasyPay callbacks. Funnel
requires MagicDNS, tailnet HTTPS certificates, and a tailnet policy that allows Funnel
on the test node. Have the tailnet admin approve it if needed. Check
`tailscale funnel status` first and don't replace an existing listener.

1. Keep Odoo on loopback with database listing disabled. Use a simple test database name
   (letters, digits, hyphens) for the database filter. Run in its own terminal:

   ```bash
   TEST_DB=easypay-test
   osh odoo --no-dev -d "$TEST_DB" --http-interface=127.0.0.1 --http-port=8177 \
     --db-filter="^${TEST_DB}$" --no-database-list
   ```

2. Run a loopback reverse proxy on port `8178` that forwards only POST to the three
   exact paths, without stripping their prefixes. For example, with Caddy, use this
   `Caddyfile` and run `caddy run --config Caddyfile --adapter caddyfile` in a separate
   terminal:

   ```caddyfile
   {
       admin off
   }

   http://:8178 {
       bind 127.0.0.1
       @easypay {
           method POST
           path /payment/easypay/webhook/generic /payment/easypay/webhook/authorisation /payment/easypay/webhook/transaction
       }
       handle @easypay {
           reverse_proxy 127.0.0.1:8177
       }
       handle {
           respond 404
       }
   }
   ```

3. Publish the **proxy**, not Odoo, with `tailscale funnel http://127.0.0.1:8178`. Copy
   the printed HTTPS URL into `WEBHOOK_BASE`. From outside the tailnet, verify that `/`,
   `/web/database/manager`, and GET on a webhook route return `404`:

   ```bash
   WEBHOOK_BASE=https://your-node.your-tailnet.ts.net
   curl -i "$WEBHOOK_BASE/"
   curl -i "$WEBHOOK_BASE/web/database/manager"
   curl -i "$WEBHOOK_BASE/payment/easypay/webhook/generic"
   curl -i -H 'Content-Type: application/json' --data '[]' \
     "$WEBHOOK_BASE/payment/easypay/webhook/generic"
   ```

   The POST must return Odoo's JSON `400` with `malformed payload`. This confirms
   routing without matching or changing a transaction. Repeat for `authorisation` and
   `transaction`. A successful probe does not prove EasyPay delivery.

4. In the EasyPay **sandbox** backoffice, open **Developers > Configuration API 2.0 >
   [payment account] > Notifications**. Verify which account owns the API key and notification
   settings there. The API Account ID used to authenticate may differ from the beneficiary/payment
   account UUID returned by `GET /2.0/config`. Verify that UUID against the sandbox backoffice
   before making changes. Save the existing `generic`, `authorisation`, and `transaction`
   URLs (the **Generic**, **Authorisation**, and **Payment** fields respectively) before
   replacing them with the corresponding paths under `WEBHOOK_BASE`. The change affects the
   whole sandbox account. Do not point Odoo's own base URL at this webhook-only proxy.

5. Complete a fresh Multibanco checkout from the local Odoo UI. Compare the issued
   reference expiry with the configured value. In the EasyPay sandbox backoffice, open
   the single payment and select **Test Payment**. Confirm that Odoo receives the
   webhook and moves the transaction from **Pending** to **Done**. Restore the original
   sandbox URLs, then stop the foreground Funnel with Ctrl+C and stop the dedicated
   proxy and Odoo server.

### Test Case 1 — Card payment (checkout flow, immediate)

1. Add an item to cart and proceed to payment
2. Select EasyPay, click **Pay Now**
3. **Expected:** Redirected to `/payment/easypay/checkout` — spinner shown, then SDK
   form appears
4. Select **Credit/Debit Card**, enter test card details
5. **Expected:** `onSuccess` fires → POST to `/payment/easypay/checkout/success`
6. **Expected:** Odoo transaction state → **Done**
7. **Verify in Odoo:** Transaction has `provider_reference`, `easypay_transaction_id`,
   `easypay_capture_status = "paid"`

### Test Case 2 — MB WAY (async, user confirmation required)

1. Proceed to payment, click **Pay Now**
2. Select **MB WAY**, enter a valid Portuguese mobile number
3. **Expected:** `onSuccess` fires → POST to `/checkout/success`
4. **Expected:** Transaction → **Pending** until the MB WAY app confirms, then webhook →
   **Done** (or **Error** on rejection)
5. Confirm (or reject) on the MB WAY app

### Test Case 3 — Multibanco (very async)

1. Proceed to payment, click **Pay Now**
2. Select **Multibanco**
3. **Expected:** SDK displays Entity + Reference + Amount
4. **Expected:** `onSuccess` fires → POST to `/checkout/success` → transaction →
   **Pending** (entity/reference stored from the authenticated read)
5. Close the browser tab
6. Simulate ATM payment using EasyPay test tools or wait for test webhook
7. **Expected:** Webhook → transaction → **Done**
8. **Retry guard test:** Before paying, go back and click **Pay Now** again
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
3. **Expected:** `onSuccess` fires → POST to `/checkout/success`
4. **Expected:** `payment.token` record created in Odoo (visible on transaction)
5. **Verify:** Token has `provider_ref` = the EasyPay payment id from the authenticated
   read

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

| Issue                                  | Solution                                                                                                               |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| SDK not loading                        | Check CDN availability; `onerror` on the `<script>` tag shows `#payment-error` div                                     |
| `testing` flag mismatch                | Provider state **Test** → `api.test.easypay.pt` → `testing: true` auto-set                                             |
| `checkout-expired`                     | User hit 30-min limit; `history.back()` lets them restart                                                              |
| Multibanco not confirmed               | Check webhook delivery to the public webhook URL; verify the notification URLs saved in the EasyPay sandbox backoffice |
| _"Payment already in progress"_        | An earlier Multibanco/MB WAY session is open; pay it or wait for expiry                                                |
| Payment status stuck on Pending        | Webhook not reachable at the public URL; check the EasyPay sandbox notification URLs point at the `WEBHOOK_BASE` paths |
| No `easypay_transaction_id` on Done tx | Webhook payload lacked `capture.id`; refund will fail with validation error                                            |
| `reference` missing in session         | `processingValues.reference` not passed from JS form                                                                   |
| Refund stuck on Pending                | Transaction webhook not received; check webhook config and delivery                                                    |
