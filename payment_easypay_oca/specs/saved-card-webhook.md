# Saved-card webhook fallback

**Status:** implemented and verified in the EasyPay sandbox

## Context

A live EasyPay sandbox run of a frequent (saved-card) checkout completed on EasyPay's
side — the checkout reached a tokenized state — but the customer's browser never
returned to Odoo: the success POST was blocked, so Odoo still showed the transaction as
draft with no payment token and no capture. EasyPay did deliver a generic webhook, which
Odoo acknowledged with HTTP 200 but could not act on. The captured sandbox HTTP log did
not record the webhook payload's `type` value, so the `frequent_create` event shape
handled here follows EasyPay's documented generic webhook payload; the live replay task
below confirms the real shape.

## Contract

- The checkout creation request must send the merchant payment key as `payment.key`
  (documented merchant payment key). It is independent from `order.key`, which already
  carries the Odoo transaction reference. Until now `payment.key` was not sent at all.
- The `frequent_create` generic webhook event carries the merchant key and the EasyPay
  payment ID. Both are **untrusted hints** used only to locate the local transaction and
  decide what to read back.
- The webhook must then authenticate: read the checkout and the frequent payment, and
  verify checkout binding, amount, currency, and an active card method before creating
  the `payment.token` and submitting the initial capture.
- Idempotency: a repeated webhook, or a later valid browser return to
  `/payment/easypay/checkout/success`, must not create a second token or a second
  capture. Once recorded in Odoo, the initial capture must not be submitted again. The
  initial capture POST carries a deterministic `Idempotency-Key` derived from the
  checkout ID and payment reference. This also protects retries after an uncertain
  submission within EasyPay's 24-hour idempotency window.
- The browser success callback and the webhook share one completion helper; concurrency
  errors propagate so the request rolls back and is retried rather than being swallowed
  into an error state.

## Tasks

- [x] Regression test covering the no-browser-return flow, forged/unknown event hints,
      replay safety, and the `payment.key` payload field
      (`test_saved_card_webhook_completes_without_browser_return`).
- [x] Implementation: send `payment.key` on checkout creation; handle `frequent_create`
      generic webhook events through the authenticated checkout + frequent reads with
      the same verification rules as the browser success path.
- [x] Live sandbox replay of the saved-card flow to confirm webhook-driven tokenization
      and capture end to end.

## Live replay attempt

The sandbox accepted a new EUR 10 frequent checkout and returned the Odoo reference as
the payment key. The SDK iframe loaded, but the browser automation timed out waiting for
the card form before submitting any card data. The checkout stayed pending and Odoo
stayed draft, with no token or capture. No webhook or success callback was observed. All
three original sandbox notification URLs were restored and verified through the API.

## Successful live replay

Waiting for either the customer details step or the card form let the next checkout
complete. Playwright blocked the success POST, and Odoo did not receive it. EasyPay sent
a matching `frequent_create` event to the generic webhook. Odoo created one token and
moved the transaction to Done. The authenticated frequent payment showed exactly one
successful EUR 10 capture, matching the capture recorded in Odoo. Replaying
`frequent_create` and `capture` left the token, capture, and transaction state
unchanged.

The generic webhook arrived about 4 minutes 46 seconds after card submission. Keep the
tunnel registered until the matching delivery arrives, with a bounded timeout and
guaranteed restoration. All three original notification URLs were restored and verified
through an independent API read.
