# Salary payments by SEPA — spec

**Status:** draft
**Date:** 2026-11-21
**Scope:** Odoo 19; addon `l10n_pt_payroll_sepa`
**Related:** `l10n_pt_payroll/readme/SPECS.md` (draft PR #187)

## Context

This addon is a scaffold: it declares the intended dependency set but
ships no behavior. The manifest sets `installable` to `False`, and
there are no models, data, views or actions yet. The module stays
non-installable until the feature specified below is implemented and
its prerequisites are available: `l10n_pt_payroll` is itself a draft
dependency (PR #187), alongside `payroll_account` and
`account_banking_sepa_credit_transfer` on Odoo 19.

## Addon boundary

- Start with one local bridge depending on `l10n_pt_payroll`, OCA
  `payroll_account`, and OCA `account_banking_sepa_credit_transfer`. Keep
  payroll selection, payable mapping, and payment-order creation separate
  from the Portuguese bank profile from day one. Do not fork the PAIN writer.
- Reuse `payroll_account`'s payslip-to-accounting move link. First verify
  that it can produce a distinct, reconcilable net salary line per
  beneficiary, and that the payment-order flow supports its account type.
  Test posting, payment, and reconciliation together; do not reclassify a
  salary liability just to make it appear in a supplier payment selector.
  If a bridge is missing, add a generic accounting hook before building XML.
- Upstream country-neutral payable hooks to `OCA/payroll` in
  `payroll_account`. Propose a separate `payroll_payment_order` addon there
  for the run action, eligibility, duplicate protection and payment-order
  integration; do not add bank-payment to core `payroll`. Once available,
  make the Portuguese addon depend on that bridge. Any missing generic PAIN
  capability belongs in `OCA/bank-payment`.
- Keep Portuguese company/payroll mappings, use of the effective
  `hr.version.payment_bank_account_id`, and Portuguese bank/channel profiles
  in `l10n-portugal`. Define their inputs as ordinary debtor, beneficiary,
  execution date and payment-mode values; generic code must not know
  Portuguese salary-rule codes or field names.

## First release

1. An authorized payroll user reviews a finalized run and prepares a draft
   outgoing payment order with a dedicated salary mode, company-owned EUR
   debit account and explicit requested execution date. A requested bank
   execution date is not evidence of payment and does not overwrite the
   payslip Payment Date used for Portuguese payroll and reporting.
2. Pay only posted, unpaid employee salary liabilities. Reconcile the
   eligible balances to the reviewed net pay; never infer payable amounts
   from gross pay, IRS, Social Security, or a sum of every credit on the
   accounting move. In v1 require EUR, a single company and execution date
   per file, and one approved SEPA IBAN per salary obligation. Exclude
   cancelled, reversed, settled and zero-balance items. Block missing,
   invalid or unapproved accounts, negative or inconsistent balances, and
   partially settled items for review. An IBAN need not start with `PT`.
3. Treasury reviews the beneficiary count, total, debit account and
   execution date, then generates and downloads the XML through the
   payment order. Upload and authorize separately in the bank portal.
   Download alone must not post a payment, reconcile an item, or mark it
   uploaded or paid. Verify the standard payment-order transitions that
   post/reconcile, and document that accounting workflow separately from
   bank acceptance and settlement.
4. Reserve each source payable once across active orders, including
   concurrent requests. Keep the generated file and message, batch and
   transaction references stable on re-download. Freeze the exported
   details; corrections create a controlled replacement only after
   rejection or non-submission is confirmed. Do not silently resend a
   file that might have been accepted. Limit employee bank details, amounts
   and XML attachments to authorized payroll/treasury users in the correct
   company, including payment-order, attachment and download access. Do
   not put employee tax IDs, payslip details or full IBANs in logs.

## Portuguese bank profile and release gate

- Start with one named bank and upload channel, not a universal Portuguese
  XML setting. The EPC baseline uses `pain.001.001.09`. The Portuguese
  C2PSP manual is the domestic reference; novobanco's public salary page
  still lists `.03` and PS2. Treat that as a reason to confirm the active
  channel with the bank, not as evidence that every channel accepts `.03`
  or rejects `.09`.
- Configure `SALA` as the salary category purpose on the payment order
  lines; the OCA SCT exporter already groups and writes `CtgyPurp/Cd`.
  Confirm its exact requirement and placement, namespace/version, debtor
  and initiating-party identifiers, address/BIC rules, batch booking,
  charset, references, cutoffs and amount/transaction limits from the
  selected bank's current guide and sample. Do not invent defaults for
  bank identifiers or assume the Portuguese NIPC is the initiating-party
  ID. Add a legacy XML profile only if needed; PS2 is out of scope.
- Validate the XML against the selected XSD, then profile-specific rules:
  salary category, account and date, exact EUR cents, counts and control
  sums, unique references, and no mixed supplier payments. Use synthetic
  fixtures and an accepted sample from a bank validator or supervised
  channel acceptance test. Passing the XSD alone is not bank acceptance.

Sources: [Portuguese C2PSP manual v06.01 (Santander)](https://www.santander.pt/pdfs/pdfs-empresas/netbanco-empresas-ajuda-online/netbanco-empresas-ajuda-online-documentos/sepa/manual_c2b.pdf),
[EPC SCT C2PSP guidelines](https://www.europeanpaymentscouncil.eu/document-library/implementation-guidelines/sepa-credit-transfer-customer-psp-implementation-1),
[novobanco salary payments](https://www.novobanco.pt/empresas/tesouraria/pagamentos/pagamentos-ordenados),
and [OCA SCT exporter](https://github.com/OCA/bank-payment/tree/19.0/account_banking_sepa_credit_transfer).

## Tasks

- [ ] Select the pilot bank and channel; obtain the current layout and a
      sanitized accepted fixture.
- [ ] Prove the payslip-to-payable-to-payment flow with an installed OCA
      19.0 stack. Test a normal run and an off-cycle payment, including
      multiple distinct obligations for one employee without merging them.
- [ ] Specify the security and release workflow before building the bridge.
      Test duplicate and concurrent generation, re-download, rejection and
      replacement, and cross-company/user access to the actual XML.
- [ ] Implement the generic bridge and Portuguese profile separately, then
      verify XSD, exact totals and bank acceptance before enabling production.
- [ ] Submit the reusable payroll pieces upstream as independent PRs.

Direct bank submission, free-form payslip-to-XML export, split or non-EUR
payments, automatic status-file import and bank reconciliation are out of
scope for the first release.
