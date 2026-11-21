# Multibanco sandbox end-to-end test

**Status:** in progress **Date:** 2026-11-21

## Contract

- Run on demand, outside Odoo's standard test discovery, against a dedicated sandbox
  account and a prestarted, isolated Odoo test instance with cron off.
- Require an explicit write opt-in, a verified payment-account UUID, and a webhook-only
  HTTPS endpoint. Snapshot the three original notification URLs to a private local file
  before changing them.
- Use the real Odoo payment form and EasyPay sandbox SDK to issue one EUR 10 Multibanco
  reference. Verify the configured seven-day expiry from EasyPay and require the
  matching Odoo transaction to be pending before settlement.
- Close the checkout browser before asking the operator to use Test Payment. Never
  simulate a webhook or change the Odoo transaction directly. Success requires the same
  reference to become paid in EasyPay and done in Odoo.
- Bound the settlement wait. Restore and verify the previous URLs on exit, including
  failure and Ctrl+C. Do not overwrite unexpected concurrent edits.

## Decisions

- Leave settlement manual: EasyPay documents the backoffice action, not a public
  simulation API. Do not automate a backoffice login.
- Reuse the documented loopback server and proxy setup rather than installing or
  starting tunnel infrastructure from the test itself.

## Tasks

- [x] Specify the safety gates and acceptance criteria.
- [x] Add the opt-in runner and document the operator workflow.
- [x] Check the write gate, URL restoration, and concurrent-edit protection offline.
- [ ] Verify the runner with a real sandbox settlement.
