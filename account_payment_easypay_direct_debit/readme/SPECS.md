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

## Tasks

- [x] Cover authenticated settlement and inconclusive reads in both paths.
- [x] Verify both addons together on the stacked branch (62 offline tests).
- [x] Review submission and retry behavior before publication.
- [x] Make ambiguous submissions recoverable without resending after the
  provider's idempotency window.
- [x] Require verified active mandates and keep capture acknowledgements
  pending until reconciliation.
- [ ] Exercise a mixed batch and concurrent upload in independent transactions
  before publishing the stacked branch.

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
