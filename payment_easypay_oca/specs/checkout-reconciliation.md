# Checkout and capture reconciliation

**Status:** in progress

## Contract

- Create at most one checkout for an Odoo transaction. Reuse a draft checkout only when
  the browser already owns its manifest. Never replace a stored checkout automatically;
  its payment may still settle. Use a deterministic creation key for concurrent requests
  or uncertain responses.
- Browser abandonment must not change payment state. Only EasyPay can confirm a
  cancellation.
- An uncertain initial capture submission must remain retryable with the same key. Do
  not commit the token and move the transaction to a terminal state merely because the
  request timed out.
- Normalize flat capture events as capture hints. Both polling and webhooks verify the
  capture ID, merchant reference, amount, and payment binding before applying a final
  outcome.
- Serialize manual capture and void on the local transaction before submitting them.
  Retrying an uncertain request uses the same key; a confirmed failed void permits a new
  attempt.
- A token-backed offline transaction may have stored its capture ID in
  `provider_reference`. Bind that capture to the locally stored token's payment ID. Do
  not implement Direct Debit in this addon.
- Sync may unlink methods from one provider, but must not disable a method still linked
  to another enabled provider.
- The Multibanco runner waits for the issued reference page, not the generic payment
  status page.

## PR #185 integration

The Direct Debit addon at `8b89fdec` installed against the #184 worktree in an isolated
database. Of its 15 offline tests, 13 passed and two webhook tests returned HTTP 503.
Their capture fixtures provide only a status, without the identity and amount required
for verification.

On #185, update those fixtures to model the authenticated capture and frequent payment
reads. Replace the test that trusts the event status with one that expects retry and no
state change when the API read is inconclusive. Store the frequent payment ID separately
from the capture ID, including for standalone mandates without an Odoo token, and remove
the obsolete webhook override.

## Tasks

- [x] Regression coverage and offline verification.
- [x] Production changes and Multibanco runner adjustment.
- [x] Run the unchanged PR #185 suite against #184 and record incompatibilities.
- [ ] Recheck integration after PR #185 adopts the verification contract.
- [x] Run the [saved-card sandbox replay](saved-card-webhook.md).
- [x] Run the [Multibanco sandbox check](multibanco-sandbox-e2e.md).
