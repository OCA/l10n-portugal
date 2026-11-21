Planned configuration checklist. None of this is available yet; the
module ships no configuration screens.

- Install the prerequisites on Odoo 19: `l10n_pt_payroll` (draft,
  PR #187), `payroll_account` and
  `account_banking_sepa_credit_transfer`.
- Set up a company-owned EUR debit account for salary payments and a
  dedicated SEPA payment mode for the salary run.
- Select one bank and upload channel. Use the EPC
  `pain.001.001.09` baseline; only use `.03` if the bank's current
  guide requires or accepts it for that channel.
- Configure the `SALA` salary category purpose on the payment order
  lines. Addresses, initiating-party identifiers and batch-booking
  options are set only as the selected bank's guide requires; do not
  invent defaults.
- Ensure each salary obligation has a posted, reconcilable liability
  and an approved SEPA IBAN on the employee's effective employment
  version (`hr.version.payment_bank_account_id`).
- Restrict payroll and treasury access: salary payment orders, bank
  details and XML downloads are limited to authorized payroll and
  treasury users in the correct company.
- Gate the release on a synthetic sample file validated against the
  bank's accepted fixture or validator.
