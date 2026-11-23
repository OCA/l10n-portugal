# Employee Payroll Payment Method

**Status:** Accounting setup implemented (verified locally); SEPA export deferred
**Date:** 2026-11-21 **Scope:** Portuguese payroll configuration on employee contract
versions and a separate Accounting integration.

## Context

Payroll needs to record how the employee's net salary is to be paid. This choice is
separate from meal allowance payment and from the bank account or salary allocation
maintained in standard Odoo.

## Original requirements

- Show **Payment Method** under **Employee > Payroll > Portugal: Salary Payment** for
  Portuguese companies, with normal HR Manager permissions.
- Provide **SEPA Bank Transfer**, **Cheque**, **Cash**, and **Other**. Use a selection
  for these categories; company-specific routing remains out of scope.
- Store the method on `hr.version`. A new version copies the prior choice unless the
  user changes it. Leave it unset by default; an IBAN or an existing payslip does not
  imply a method.
- Saving a method does not change bank accounts, require an IBAN, affect a payslip
  calculation, generate a payment file, or record a payment.
- Demo data illustrates SEPA, cheque and cash on three named Portuguese employees.

## Original acceptance

- A new employee has no method until one is explicitly set.
- Updating the field on the employee form edits the selected contract version. A dated
  change preserves the method on earlier versions.
- Cash and cheque can be recorded without a bank account. Bank validation belongs to a
  future payment workflow and must not block saving the preference.

## Accounting setup

Main `l10n_pt_payroll` owns the editable choice. It uses core Accounting without
depending on OCA payment modes or the SEPA exporter.

- Store an outbound `account.payment.method` as `payment_method_id` on `hr.version`.
  Preserve existing Accounting-backed assignments on upgrade. Accounting methods are
  shared records, not company-specific journals. Do not create duplicate methods or pin
  the employee to a journal. Cheque and SEPA methods are available when their Accounting
  addons provide them. Manual cash payment uses the standard outbound manual method and
  a cash journal.
- Leave existing choices untouched on installation. Show the legacy value read-only
  until an HR Manager explicitly selects a method confirmed by Accounting for that
  employer and version. Do not infer a match from the choice, mode name, or IBAN.
- Select one **Salary Bank Account** from **Personal > Bank Accounts** on the contract
  version (`payment_bank_account_id`). It is optional and does not change standard
  Salary Allocation. Reject a new assignment unless the account is active, belongs to
  the employee's Work Contact, is in the employee's bank account list, and is shared or
  belongs to the employer. Keep historical references if accounts are later removed from
  the list or archived. Never fall back to another account.
- **Add Bank Account** creates one standard `res.partner.bank` on the employee's Work
  Contact, adds it to the employee's existing list, and selects it on the version being
  edited. Use the normal bank creation permissions. Do not mark it trusted or copy the
  number to another record.
- The selector also offers **Create and Edit** on saved employees with a Work
  Contact. The creation form fixes the account holder to that contact. Saving
  it adds the account to the employee's list immediately. Saving the employee
  form records the selected account on the version.
- Both entry points open the same bank account form, including the optional
  Bank field. The button still selects the saved account immediately.
- The picker offers outbound methods only. Validate direction on ORM assignment too.
  Check company scope when the export resolves the payment mode and funding journal, not
  by filtering the shared method catalog.

## SEPA export follow-up

- Implement payment order preparation and SEPA file generation in a **separate optional
  addon** that depends on `l10n_pt_payroll`, the payroll accounting bridge, and OCA
  `account_banking_sepa_credit_transfer`. Base payroll does not depend on SEPA export.
- Use the method from the finalized payslip's linked contract version, not the
  employee's current version. If a pay obligation spans different payment instructions
  and has not been split by payroll accounting, require review rather than guessing.
- Use the version's selected salary bank account. At preparation time, revalidate
  ownership, membership in the employee's bank accounts, status, trust, IBAN, currency
  and amount. Do not silently choose another account. Split payouts remain a separate
  design decision.
- Prepare an Accounting payment order from the finalized, posted salary payable items
  for one company and the selected SEPA mode. Resolve the employer's funding journal
  from that mode. Reuse `account_banking_sepa_credit_transfer` to generate the bank's
  configured `pain.001` format. Generate through the normal Accounting review flow;
  preparing a draft must not submit to a bank, mark a payslip paid, or silently generate
  a second order for the same payable.
- The current OCA Payroll 19.0 checkout contains `payroll`, not a salary accounting
  connector that provides posted payable items linked to payslips. Verify or implement
  that source before wiring order preparation. Keep the OCA bank-payment dependency in
  an optional integration addon so the base localization can still run without payment
  orders.

## Integration acceptance

- An employee can have distinct salary payment methods on two dated versions. Non-SEPA
  methods never produce lines in a SEPA order.
- Preparing an order from the same payable twice cannot create duplicate transfer
  instructions. Missing or conflicting bank data blocks preparation with a reason; it
  does not silently omit a SEPA employee.
- A mixed batch yields a reviewable EUR total matching eligible outstanding salary
  payables. The configured Accounting generator produces a `pain.001` that validates for
  the employer's chosen bank format.

## Tasks

- [x] Implement and verify the field, form, and demo values.
- [x] Implement the core Accounting-backed assignment, legacy review, and salary bank
      account display.
- [ ] Verify the posted salary payable source and build the separate SEPA export addon.
- [x] Verify the bank account selector, creation on the employee contact, and
      preservation of historical selections.

## Decision log

- 2026-11-21: Supersede the optional setup addon backed by OCA `account.payment.mode`.
  Use core `account.payment.method` in main Payroll to avoid making the LGPL addon
  depend on an AGPL addon. Keep company-specific routing and SEPA generation in the
  separate export addon.
- Use generic payment fields and a generic bank-account creation wizard so they can move
  upstream later. They stay in `l10n_pt_payroll` for now.
