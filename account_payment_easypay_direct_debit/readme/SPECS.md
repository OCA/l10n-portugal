# Direct Debit settlement

**Status:** in progress

## Contract

- A submitted debit stores the frequent payment ID as the provider reference
  and the capture ID separately. This applies when there is no Odoo token.
- Before applying an outcome, verify the capture ID, merchant reference,
  amount, and binding to the locally recorded frequent payment. The webhook
  also verifies the frequent payment's currency through EasyPay.
- An inconclusive read leaves a debit pending. Webhooks request redelivery
  rather than trusting an event's status. Repeated verified notifications
  do not create another debit.
- The poller only handles this addon's offline Direct Debit transactions;
  it cannot change the state of other token-based payments.
- Before submitting a capture, read the mandate from the selected EasyPay
  account. Require the matching frequent payment ID and an active Direct
  Debit method. A locally cached active status does not authorize a debit.
- A successful capture POST (`status: ok` and a capture ID) acknowledges
  submission. Record it as pending, regardless of any settlement details
  in the response. A verified capture read is required to settle it.
- Token reuse requires an active Direct Debit token from the mandate's
  company and commercial customer. The verified remote mandate must bind
  to the same bank account. A debit may be submitted only for a locally
  valid mandate and its registered provider.
- Accounting users may perform their authorized workflows without reading
  the API key. Check model access and the provider's company and state
  before narrowly elevating the provider request.
- Authenticated webhooks and polling interpret Direct Debit capture outcomes
  identically. A verified late return moves a Done debit to Cancel and
  reopens accounting follow-up. Poll recent completed debits once per day
  for 60 days as a fallback; webhooks remain authoritative beyond that.
- This addon submits debits from payment orders. It does not offer Direct
  Debit checkout or generate online tokens.

## Tasks

- [x] Cover authenticated settlement and inconclusive reads in both paths.
- [x] Verify both addons together on the stacked branch (75 offline tests).
- [x] Review submission and retry behavior before publication.
- [x] Make ambiguous submissions recoverable without resending after the
  provider's idempotency window.
- [x] Require verified active mandates and keep capture acknowledgements
  pending until reconciliation.
- [x] Exercise a mixed batch and concurrent upload in independent transactions
  before publishing the stacked branch.
- [x] Cover an ordinary accounting user's registration, mandate ownership,
  local cancellation, verified late returns and both preparation windows.

## Remaining publication blocker

- An upload failure can roll back local tracking for debits that EasyPay
  already accepted. EasyPay retains idempotency keys for 24 hours, so the
  same key alone cannot safely authorize a later resend. Verify recovery
  after a lost response and after partial success at the upload boundary.

## Submission recovery design

- Reserve each debit in Odoo before making a capture POST. Persist the
  merchant reference, provider, frequent payment, amount and currency, and
  a retry deadline tied to the reservation. Do not commit the upload RPC
  midway through the order. Submit reserved debits from a separate worker
  transaction after the reservation commits.
- A worker serializes each reservation and retries an unacknowledged debit
  with the same key and payload only within a conservative window shorter
  than EasyPay's 24 hours. A worker crash must not erase the reservation.
  Never resend a debit with a verified capture ID.
- After the deadline, reconcile by authenticated provider evidence or have
  an operator investigate. An empty or incomplete provider result is not
  permission to resend. Keep the order from posting and reconciling its Odoo
  payments until all its debits have been acknowledged.
- Exercise a mixed batch with one accepted debit and one lost response.
  Re-run after rolling back the worker transaction, both inside and outside
  the retry window. Assert that neither a second operator click nor a
  concurrent worker can create a new debit for an unresolved reservation.

### Use the existing payment order steps

Use the Generate step to reserve, without network writes. Use the later
Mark as Uploaded request to submit those existing reservations. This gives
the database a commit boundary without a new worker or a mid-request commit.
The usual controls remain in the same order.

- Generate freezes the payment identity and capture payload. An upload
  without reservations is blocked, not implicitly reserved and submitted
  in the same request. A successful acknowledgement is never resent.
- An unacknowledged reservation may submit or retry for 23 hours from
  creation. This is deliberately earlier than the provider's 24-hour
  expiry even if the first submission was delayed. After the deadline
  no capture POST is allowed, including on a repeated upload click.
- Order cancellation or regeneration must not discard reservations that
  could have reached EasyPay. Preserve the original merchant reference
  for operator reconciliation. Do not add an automatic reset for an
  ambiguous debit.

The offline suite verifies that an upload rollback preserves the reservation,
that a later retry uses the same request, that expiry blocks another POST,
and that a capture recovered by webhook is not resubmitted on upload.
The mixed-batch regression covers two accepted debits with one lost
response. Within the retry window both requests replay without creating
new captures. After expiry neither request is sent. A separate offline
probe with two real PostgreSQL transactions verified a single capture
POST and an already-uploaded result on retry after a serialization error.

### Separate unsent from uncertain

Supersedes measuring the retry window from Generate. Generate creates unsent
reservations, which do not expire. Prepare EasyPay Upload records the start
of the 23-hour window in a separate request without sending any debit.
Upload requires that durable marker. Orders that have not been prepared
and have no capture ID may be cancelled or regenerated. A prepared order
must retain its reservations and cannot silently start a new window.

### Standalone mandate registration

Prepare EasyPay Registration durably pins the request and the EasyPay
account without making a remote write. Validate checks local prerequisites,
then uses one stable idempotency key and the same request for at most 23
hours from preparation. Changes to the mandate payload or account block
submission; they do not reset the attempt. After an ambiguous expiry, an
administrator may recover a known frequent payment by authenticated ID,
original merchant key, active Direct Debit method and matching IBAN. Never
automatically register a second mandate to recover a lost response.

## Live sandbox verification (2026-11-23)

Verified against `api.test.easypay.pt` from an Odoo 18 database with one
synthetic partner, one valid test IBAN and a EUR 10 frequent-payment
debit:

- `POST /2.0/frequent` registered the mandate; EasyPay initially reported
  the method status as `waiting` and flipped it to `active` within about
  a minute. The 23-hour upload retry window absorbs this activation
  delay; an immediate Upload correctly refused to debit an unconfirmed
  mandate.
- EasyPay returns `method.type` as `DD` (uppercase) while the request
  vocabulary is `dd`. Mandate verification must compare case-insensitively;
  the fixtures were updated to the real response casing.
- `POST /2.0/capture/{frequent_id}` returned a capture UUID; Odoo stored
  it and left the transaction `pending` — acknowledgement is not
  settlement.
- An authenticated `GET /2.0/capture/{id}` through the polling path
  verified identity, reference, amount and payment binding; EasyPay
  reported status `waiting`, which maps to `pending`.
- Settlement was still `waiting` at the end of the session; EasyPay
  documents up to 14 days for Direct Debit confirmation. Whether the
  sandbox auto-settles or requires a backoffice action remains open.
