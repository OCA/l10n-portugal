# IRS withholding (retenção na fonte) — spec

**Status:** in progress — models, retention engine, 2026 CSVs for all three regions and
the official-xlsx converter implemented and verified **Date:** 2026-11-12 (updated
2026-11-20) **Scope:** `l10n_pt_payroll` in OCA/l10n-portugal. Owns the IRS retention
determinants on `hr.version` (moved here from `l10n_pt_hr`), the yearly table values and
the retention computation; `l10n_pt_hr` keeps only `l10n_pt_disability_degree` (also
needed by DMR-AT) and the `l10n.pt.irs.withholding.table` variant list. **Related:**
`l10n_pt_hr/readme/SPECS.md`, `l10n_pt_hr/readme/CONFIGURE.md`
(employee-side catalog).

## Context

`l10n_pt_payroll` computes IRS retention with the official withholding tables approved
each year by Despacho (e.g. n.º 233-A/2026 for the continente, n.º 1179/2026 for the
Açores, Despacho n.º 19/2026 RAM for Madeira, all for 2026). Each region publishes its
own I–XI tables; the tables change every year — sometimes mid-year (2026 saw a
retroactive rate cut via Decreto-Lei n.º 212/2026 and a November half-retention month
via Despacho n.º 12523-A/2026).

The module must make updating them cheap: the official tables ship as CSVs generated
from the AT Excel files, and an administrator can import a newer or corrected file
manually without a module release.

## Implemented so far

- `hr.pt.irs.withholding.table` — one bracket set per (date_start, region, table
  variant): `date_start`/`date_end` vigência, `region`, `table_id` →
  `l10n.pt.irs.withholding.table` (I–XI), set-level Despacho constants (`ias`,
  `disabled_dep_parcela_single`/`_joint`, `spouse_disabled_parcela`,
  `pension_dep_parcela_single`/`_joint`/ `_single_income`) and `line_ids`.
- `hr.pt.irs.withholding.line` — one bracket: `lower_bound`, `upper_bound` (empty =
  open-ended), `marginal_rate`, `parcela_abater` (safe_eval expression in `R`),
  `dependent_parcela`, `forces_disabled_parcela` (armed-forces pensioner flat deduction,
  tables X/XI), `effective_rate_limit` (informational).
- Retention engine on `hr.payslip._l10n_pt_irs_retention`, called by the `IRS` salary
  rule; `l10n_pt_irs_taxable` on `hr.salary.rule` is the share (0-1) of each rule total that enters `R`
  (currently only `BASIC`).
- `hr.pt.irs.withholding.import` wizard hosting the whole CSV import
  pipeline (`_import_csv_data` + validation/upsert helpers), the bundled
  loader and `post_init_hook` loading `data/irs/*.csv`.
- Bundled `data/irs/2026_{continente,acores,madeira}.csv` generated from the official AT
  workbooks (`Tabelas_RF_*_2026.xlsx` on the Portal das Finanças doclib) with
  `scripts/xlsx_to_csv.py`: 106/98/104 brackets, 11 variants each.
- `hr.version` IRS fields + tests (see below).
- Social Security rules driven by the employee's regime: `SS` (employee TSU)
  and `SS_COMP` (employer TSU) apply the employee and employer rates from
  `l10n.pt.ss.regime.l10n_pt_employee_rate` / `l10n_pt_employer_rate`
  (fields owned by `l10n_pt_hr` together with the regime records and their
  official values) to the contribution base; `SAT_COMP` uses the `rate`
  field of the employee's `l10n.pt.work.insurance` policy (0 when no
  policy). The starter rules use BASIC; eligible earnings can be
  included through the salary-rule Social Security base configuration.
  FGS was abolished and is not modeled.
- The hidden PT_SS_BASE rule stores the contribution base for reconciliation.
  Both contribution rules use that same result at calculation precision; the
  stored payslip line uses standard Payroll precision and does not affect
  gross, net, or declarations.

## Payroll roadmap

### Christmas subsidy: first supported workflow

- Pay one current-year subsidy on a regular November payslip or a standalone
  December payslip. Use the same opt-in `PT_NATAL` input on both structures.
  Never create a payment based on the month alone. An off-cycle final settlement
  can use the input too.
- Payroll enters the reviewed gross entitlement, including eligible seniority
  pay and any required proration under Labour Code Articles 262 and 263.
  A full-year initial example is one monthly base plus seniority; admission,
  cessation, suspensions and collective agreements require review. No automatic
  entitlement calculation, prior-year payments or instalments in this release.
- Store the gross amount on `PT_NATAL` (DMR-AT A4, Social Security N). Include
  it in gross, employee contributions and employer contributions. Compute
  `PT_NATAL_IRS` autonomously under CIRS 99-C, using the actual Payment Date,
  employee determinants and subsidy amount only. Exclude both Natal lines
  from ordinary IRS history. For non-residents with a single-payer declaration,
  stop for manual review rather than guessing the separate allowance treatment.
- Require an explicit Payment Date in the entitlement year (identified by
  the payslip period end). The normal private-sector deadline is 15 December.
  A late payment remains recordable. Use only one positive payment per employer,
  employee and year. Refuse another payment if an earlier one is finalized.
  Prior external payments and reversals require manual review. Confirm
  overlapping payroll runs sequentially.
- A regular payslip with EUR 1,400 ordinary pay and EUR 1,400 subsidy, with a
  20% test bracket up to EUR 2,000, must show EUR 280 of IRS separately on each
  payment, and use EUR 2,800 as its Social Security base. A standalone payslip
  for the same subsidy must not include ordinary pay or IRS.

#### Natal balance calculation

This supersedes the earlier once-per-year prohibition. Keep Natal policy
in salary-rule code. Reuse generic payroll history and autonomous IRS helpers
instead of adding Natal-specific methods to `hr.payslip`.

- Interpret the input as the reviewed **total gross entitlement for the year**,
  not the balance due. Sum prior finalized Natal earnings in the entitlement
  year for the same employee and employer, across contract versions.
- Show the annual entitlement as `PT_NATAL` and prior payments as a
  separate negative `PT_NATAL_CORRECTION` earning. Their sum is the
  current payment for gross, net, Social Security and declaration income.
  Future history sums both codes. A future export must net them under
  A4/N rather than report the correction as a separate payment.
- If EUR 900 was already paid against a revised EUR 1,400 entitlement, the
  next payslip pays EUR 500. If the full entitlement was already paid, pay
  zero. An overpayment is a correction case, not a negative earning.
- Under CIRS Article 99-C(5)-(6), compute withholding autonomously on the
  full subsidy. A top-up pays the entire remaining balance, so the
  cumulative share reaches 100%. Subtract Natal tax already withheld
  from the full subsidy tax. Do not use the balance to select a bracket
  or include it in ordinary monthly IRS. A negative tax adjustment
  requires manual review rather than an automatic refund. Scheduled
  partial payments are still out of scope.
- The separate correction line supersedes the custom freshness check.
  Use standard OCA Compute on Confirm and confirm sequentially. If
  recomputation is disabled, recalculate immediately before confirming;
  no extra guard catches stale drafts. Out-of-order payments, external
  payments and reversals require manual review.

#### Natal in duodécimos

This supersedes the initial exclusion of scheduled partial payments.

- Opt in on each monthly payslip with `PT_NATAL_MONTHLY` in Other Inputs.
  Enter the reviewed full annual entitlement. Do not also enter `PT_NATAL`.
  The existing lump-sum and settlement workflows remain available.
- The installment is one twelfth, distributing residual cents by taking
  the difference between the rounded scheduled totals at the end and
  beginning of the payment month. Subtract finalized installments in that
  payment month and cap the result at the unpaid annual balance. Do not
  automatically catch up missed months. Require Payment Date in the period
  year. Use standard Compute on Confirm and confirm sequentially.
- Include only the installment actually payable in gross, Social Security,
  and declaration income (A4/N). Store the full basis in a hidden helper.
  The autonomous IRS for each installment is its fraction of the tax
  calculated on the full entitlement at the payment date, rounded to cents.
  Do not retrospectively apply a changed tax table to installments already
  paid. See [OCC guidance on withholding on installments](https://www.occ.pt/pt-pt/noticias/irs-retencao-na-fonte-de-subsidios-de-ferias-e-de-natal).
- A later lump-sum settlement subtracts both prior installments and net
  lump-sum earnings; if installments exist, apply the full-entitlement
  effective rate only to the current balance. Continue to flag reversals
  and out-of-order payments. External payments, pensioners and non-residents
  with the single-payer declaration still require manual review.

### Subsídio de Férias

- Keep the subsidy separate from paid annual leave and Natal. Under
  [Labour Code Article 264](https://diariodarepublica.pt/dr/lexionario/termo/subsidio-ferias),
  payroll schedules payment before leave starts, proportionally for split
  leave, unless a written agreement provides otherwise. Do not derive dates
  or entitlements from Time Off. Support regular and holiday-only payslips.
- `PT_FERIAS` Other Input is the reviewed gross annual entitlement. The
  optional `PT_FERIAS_TARGET` is the cumulative gross amount due through
  this payment, not the amount of the current installment. If omitted or
  zero, settle the full entitlement. Deduct finalized holiday subsidy
  earnings in the same payment year, employer and employee. A repeated
  target pays zero. Reject targets above entitlement, negative or duplicate
  inputs, and history above entitlement. Keep autonomous IRS and history
  independent of Natal. Require explicit Payment Date in the payslip year.
  Confirm sequentially with normal OCA recomputation.
- Store the entitlement as a hidden reference and book only the payable
  difference under `PT_FERIAS` (DMR-AT A3, Social Security F). Compute IRS on
  the full entitlement using the current payment date, then apply only the
  paid fraction rounded to cents under CIRS Article 99-C(5)-(6). Do not
  reprice earlier installments or add the subsidy to ordinary IRS. Include
  the amount paid in employee and employer Social Security.
- A reviewed EUR 1,400 entitlement with a first EUR 700 target pays EUR
  700 and withholds EUR 140 at a 20% test rate. Repeating that target pays
  nothing. A later full settlement pays the remaining EUR 700 and withholds
  EUR 70 if the effective rate then is 10%. The standalone slip has no
  ordinary earnings or IRS. A regular slip can pay both distinct subsidies.
- A cumulative target can record installments agreed in writing, including
  duodécimos. No automatic calendar, entitlement, or contract proration is
  included. Prior-year, external-payment, reversal, complex termination,
  pensioner and non-resident single-payer cases require manual review.

#### Holiday subsidy in duodécimos and separate contributions

- This supersedes manual-only duodécimos and the combined Social Security
  base for holiday subsidy. The existing Natal rules are unchanged.
- On a regular payslip, opt in with `PT_FERIAS_MONTHLY` and enter the reviewed
  full annual entitlement. Do not combine this input with either manual
  holiday subsidy input. A written agreement is required for this schedule.
- Pay the difference between rounded scheduled totals for the current and
  previous calendar months, based on Payment Date. Deduct holiday subsidy
  already paid in the payment month and cap the installment at the unpaid
  annual entitlement. No automatic catch-up. Manual settlement subtracts
  both scheduled and manual payments. Both workflows use the same earning
  and autonomous withholding lines and declaration codes.
- Keep the holiday subsidy out of `PT_SS_BASE`. Calculate its employee and
  employer Social Security on the amount actually paid, as separate lines
  at the contract regime rates. A zero installment adds no contribution
  lines. Preserve the base/rate presentation and rounding fallback.
- At the fixture's rates, a EUR 1,400 annual entitlement pays EUR 116.67
  in January and EUR 116.66 in February. January holiday contributions
  are EUR 12.83 employee and EUR 27.71 employer, and holiday IRS is
  EUR 23.33. Confirmed installments over twelve months total EUR 1,400.

### Remaining roadmap

- **Next: Automated subsidy entitlement and scheduling.** See the
  [subsidy and absence spec](../specs/leaves-and-absences.md).
- **Next: leaves and absences.** Classify paid, unpaid, and externally paid leave
  and wire the agreed deductions into payslips. Keep vacation pay separate from
  the holiday subsidy.
- **In parallel: DMR-AT.** Obtain the official upload layout and a sanitized
  validator-accepted fixture. Then build the monthly review and export, including
  the reporting treatment for both subsidies. See the [DMR-AT spec](../specs/dmr-at.md).
- **Later: overtime and employer reporting.** Use the existing statutory hourly
  rate helper for overtime. Specify Social Security and Relatório Único exports
  separately, including establishment reporting.
- **Planned: payroll accounting and SEPA.** Link posted salary payables to
  payslips before exporting them. See [Salary payments by SEPA](#salary-payments-by-sepa).

## Payroll history totals

**Status:** in progress

- Query finalized payslip lines for the same employee and employer, across
  contract versions. Use explicit inclusive date bounds, an explicit date basis,
  and requested salary-rule codes. Exclude the current slip and respect payroll
  access rules. Sum recorded values, not today's rule formulas.
- Use Payment Date for paid-income windows, with the existing period-end fallback
  where allowed. Use period end for period-based windows. A year-to-date window
  starts on 1 January; a lookback of N completed calendar months ends immediately
  before the current month. Do not conflate a rolling window with entitlement.
- `payslip._get_payroll_history_totals(codes, *, date_basis, window,
  months=None)` returns a dictionary keyed by rule code, including zero for
  missing codes. Use `payment` or `period` as the date basis. Use
  `month_to_date`, `year_to_date`, or `previous_months` as the window and pass
  a positive `months` count only for `previous_months`. The corresponding date
  on the current slip anchors the window. Same-date finalized slips count.
- Preserve signed totals, including confirmed reversals, for reporting. Keep
  policy checks separate: ordinary IRS can still block reversals or ambiguous
  dates, and a once-per-year subsidy cannot rely on a zero net total to prove it
  was never paid.
- Test payment versus period boundaries, incomplete months, year rollover,
  employer isolation, cross-version history, and reversals before reusing
  the helper for statutory calculations.
- Natal uses the year-to-date totals in strict mode, which also checks
  the rest of the year for out-of-order payments and rejects reversals.
  Ordinary IRS requests strict month-to-date withholding lines with explicit
  payment dates when prior results exist. It still validates that every
  withholding line has its two recorded helper lines.

## Salary payments by SEPA

- **Status:** draft
- **Date:** 2026-11-21
- **Scope:** Odoo 19; proposed addon `l10n_pt_payroll_sepa`

### Addon boundary

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

### First release

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

### Portuguese bank profile and release gate

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

### Tasks

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

## Spec

### Retention computation

#### Payslip presentation

- Store ordinary taxable earnings for the current payment and the single-payer
  allowance actually used on two technical salary-rule lines. Keep them
  separate from the IRS line, which stores only the increment withheld.
  The technical lines use native Amount/Rate/Total and never add pay or
  duplicate declaration amounts. Monthly IRS reads the finalized lines
  without re-evaluating old salary rules. DMR can reconcile from these
  amounts, but still needs the individual income-code breakdown.

- Social Security uses the native Amount and Rate columns for the signed
  contribution base and the applicable worker or employer rate. Include the
  rate in the line description as the standard PDF only prints the quantity.
  When column precision would change the amount, show the base and rate in
  the description instead.
- IRS keeps the final rounded withholding as the rule result. Its description
  distinguishes the applied calculation rate from the monthly effective rate
  (withholding divided by the corresponding income before relief). Show the
  monthly effective rate even when positive income results in no withholding.
- Fresh installs load the starter formulas from XML. Earlier development
  databases require a one-time refresh of the starter formulas. Do not
  rewrite existing payslip lines.
- The IRS withholding model owns dated table lookup, bracket selection, and
  the shared statutory calculation. Salary rules own what income is subject
  to each calculation. Ordinary IRS first records PT_IRS_BASE and
  PT_IRS_ALLOWANCE, then uses those values and validated monthly history.
  Both helpers keep their existing codes and remain hidden.

For each payslip:

```
R = sum of payslip line totals x l10n_pt_irs_taxable (taxable share)
table = hr.pt.irs.withholding.table covering payslip.payment_date or payslip.date_to
        for (employee region, computed table variant)
bracket = the single line with lower_bound < R <= upper_bound
rate   = bracket.marginal_rate - (1.0 if dependents >= 3 else 0.0)   # n.5-h
        → replaced by l10n_pt_irs_preferred_rate when set           # n.5-e
parcela = safe_eval(bracket.parcela_abater, {"R": R})
        + bracket.dependent_parcela * n_dependents
        + disabled_dep_parcela_{single|joint} * n_disabled_dependents * factor   # n.5-a/n.6
        + spouse_disabled_parcela                                   # n.5-b
        + pension_dep_parcela_{single|joint|single_income} * n_dependents         # n.5-c
        + bracket.forces_disabled_parcela                           # n.5-d (X/XI)
retention = max(0, R * rate/100 - parcela)  →  truncated down to the euro
```

- **Non-resident** (`l10n_pt_irs_non_resident`): apply 25% without a resident
  table lookup. Under CIRS Article 71(5)-(6), if the worker supplied the
  single-payer declaration, the payroll officer records the eligible share
  of the monthly minimum-wage allowance in Other Inputs. Enter only the
  portion available for this payment, taking into account other payments
  in the month. A missing or zero input means no allowance. Reject duplicate,
  negative, or non-finite inputs for the contract. Do not infer eligibility
  or grant a new allowance per slip. Show the amount actually applied on
  the IRS line; it is not a separate earning or deduction.
- **Preferred rate** (`l10n_pt_irs_preferred_rate`): replaces only the marginal rate
  (n.5-e); every parcela still applies.
- **Pensioner** (`l10n_pt_irs_pensioner`): resolves the VIII–XI variant through the same
  `l10n.pt.irs.withholding.table` mechanism; n.5-c per-dependent amounts and n.5-d
  armed-forces flat amount apply; n.5-a still applies per disabled dependent.
- **Disabled dependents**: n.5-a adds `disabled_dep_parcela_*` per dependent with
  disability ≥ 60%; n.6 lets the employee multiply it — up to 3× (single /
  married-single-income) or 6× (married joint), declared via
  `l10n_pt_irs_disabled_dep_factor` (constrained).
- **Disabled spouse** (n.5-b): `married_single_income` + spouse with disability ≥ 60%
  and no category A/H income → flat `spouse_disabled_parcela`.
- **Armed-forces disability** (n.5-d): pensioner + `l10n_pt_military_disabled` → flat
  `forces_disabled_parcela` on the bracket (tables X/XI only).
- **IRS Jovem** (art. 12.º-B CIRS, n.5-g): opt-in `l10n_pt_irs_jovem` + declared
  `l10n_pt_irs_income_years`. Exemption by income year: 100% / 75% (yrs 2–4) / 50% (yrs
  5–7) / 25% (yrs 8–10). Calculate the table-based effective rate on full `R`
  before applying it to `R − min(R × pct, 55 × IAS / 14)`. Round down only the
  final withholding. See AT Ofício Circulado 20274/2025 and Despacho n.5-g.
- Region resolves from `l10n_pt_irs_region` (auto-defaulted from the private address:
  state 20 → Açores, 30 → Madeira, 9xxx zip fallback). Resolve the table
  using the payslip Payment Date, falling back to the period end (`date_to`)
  when blank. Use the same date for monthly accumulation and confirmation
  order.
- No covering table → `UserError`, never a silent fallback.
- Bracket lookup must be deterministic: exactly one bracket per `R`.

### `hr.version` fields

- `l10n_pt_irs_family_status` — `single` / `married_single_income` / `married_joint`.
- `l10n_pt_irs_dependents` — IRS dependents (may differ from children).
- `l10n_pt_irs_disabled_dependents` — dependents with disability ≥ 60%.
- `l10n_pt_irs_disabled_dep_factor` — n.6 multiplier (1–3 or 1–6).
- `l10n_pt_irs_spouse_disabled` — n.5-b spouse case.
- `l10n_pt_military_disabled` — n.5-d armed-forces pensioner.
- `l10n_pt_irs_region` — `continente`/`acores`/`madeira`, computed default from address,
  manually overridable.
- `l10n_pt_irs_pensioner`, `l10n_pt_irs_non_resident`, `l10n_pt_irs_preferred_rate`,
  `l10n_pt_irs_jovem`, `l10n_pt_irs_income_years`.
- `l10n_pt_irs_single_payer_declared` — the non-resident worker's written
  single-payer declaration (CIRS art. 71) is on file.
- `l10n_pt_irs_table_id` — computed variant (I–XI), derived from family status +
  dependents + disability + pensioner flag.
- `l10n_pt_irs_taxable` Float on `hr.salary.rule` — taxable share multiplier (1.0 = fully taxable).
- Payslip input `PT_IRS_SINGLE_PAYER` records the eligible share of the
  monthly minimum-wage allowance for that payment (non-resident with
  declaration only). It replaces the draft dedicated payslip field.

Kept in `l10n_pt_hr`: `l10n_pt_disability_degree` (DMR-AT needs it).

### CSV table files

- Bundled files live in `data/irs/<year>_<region>.csv`; file name is documentation —
  columns carry the keys.
- Header:
  `date_start,date_end,region,table_code,lower_bound, upper_bound,marginal_rate,parcela_abater,dependent_parcela, forces_disabled_parcela,effective_rate_limit,ias, disabled_dep_parcela_single,disabled_dep_parcela_joint, spouse_disabled_parcela,pension_dep_parcela_single, pension_dep_parcela_joint,pension_dep_parcela_single_income`
- `table_code` is the Roman variant I–XI; `date_start`/`date_end` give the Despacho
  vigência; set-level columns repeat on every row of a block and must be consistent
  inside it.
- Portuguese number formats (`1 234,56`, `44,95%`) are normalized at import;
  `parcela_abater` accepts expressions in `R`.
- **Official source:** the AT publishes Excel files per region on the Portal das
  Finanças doclib (`Tabelas_RF_*`). `scripts/xlsx_to_csv.py` converts them into the
  bundled CSV format (`inspect` dumps the layout, `convert` emits the CSV); the Despacho
  n.5 period constants are not in the workbook and are passed via `--set-json`.
  Transcription from the DR PDFs is the fallback.
- Adding a new Despacho = new CSVs (+ manifest data entry or module release);
  corrections = manual import.
- Bundled CSVs are append-only history: never delete an old year's files. Existing
  databases keep imported sets either way (the loader never deletes), but fresh installs
  only receive what is bundled — dropping an old file would break backdated payslips on
  new databases.

### Import

- Wizard `hr.pt.irs.withholding.import` owns `_import_csv_data`: upload CSV → validate → upsert per (date_start,
  date_end, region, variant) block; "Load bundled tables" re-imports `data/irs/*.csv`.
- Validation: required columns, known region/table codes, ordered numeric bounds
  contiguous from 0, last bracket open-ended, rates 0–100, `parcela_abater` parses under
  `safe_eval`, consistent set-level values per block, no partial writes on error.
- `post_init_hook` loads the bundled files at install.

## Statutory declarations — DMR (Segurança Social + AT)

> 2026-11-21: The [DMR-AT living spec](../specs/dmr-at.md) supersedes the IRS assumptions and tasks in this section. DMR-AT and Social Security reporting are separate workflows. The Social Security design is not amended here.

### Context and legal frame

The **Declaração Mensal de Remunerações (DMR)** is a single monthly
obligation that simultaneously satisfies Segurança Social (contributions)
and the Autoridade Tributária (IRS withholding and deductions). It is
not two separate declarations: one submission reports, per worker, the
remuneration per earning code, the contribution rate code, the SS
contributions, the IRS retention, health-system and union deductions.

- Legal basis: Lei 110/2009 (Código dos Regimes Contributivos), DR
  1-A/2011, Portaria 307/2022 (SS model), Portaria 33/2024 (AT model,
  CIRS art. 119 n.1).
- Deadline: day 1–10 of the following month; August payslips extend to
  day 25. Delivery counts only when the system validates it.
- Channels: online only, via Segurança Social Direta or Portal das
  Finanças. Employers with **50+ workers must submit the file**
  ("Entregar ficheiro declaração de remunerações"); smaller employers
  may also use the portal's pre-filled/empty forms.
- Corrections: an error is fixed in the next month's declaration
  referencing the original month; later corrections need a standalone
  rectificativa (late filing).

### Data the module already owns

- `hr.version.ssnid` — NISS with PT check-digit validation (l10n_pt_hr).
- `l10n.pt.ss.regime` + `l10n_pt_dr_code` — the DR rate code per
  situação contributiva.
- IRS determinants on `hr.version` (family status, dependents, region,
  pensioner, Jovem...) and the computed table variant.
- Computed payslips with categorized lines (`BASIC`, `SA`, `SS`,
  `SS_COMP`, `IRS`, `SAT_COMP`, `NET`).

### Gaps to close

- **Earning/deduction codes**: the DMR reports remuneration per
  official *código de rendimento* (and deductions per código), not per
  salary rule. `l10n_pt_dmr_code` on `hr.salary.rule` stores the
  earning code per rule (same pattern as `l10n_pt_irs_taxable`, both
  editable on the rule form); deduction rubricas are identified by
  their rule codes/categories. Still needed: the official code table
  to populate values, and a mapping for codes not expressible per
  rule (e.g. holiday/Christmas subsidy splits, meal-subsidy taxable
  portion).
- **Worker-level DMR fields**: stored — NIF (`res.partner.vat` on the
  employee's work contact), NISS (`ssnid`), birth date
  (`hr.employee.birthday`), marital status (core `marital`), family
  status/dependents/disability (IRS fields), union + dues rate
  (`l10n.pt.union.l10n_pt_dues_rate`), regime + DR code, IRCT,
  profession, pay grade, work insurance. Remaining audit item: whether
  the AT facet needs fields beyond the IRS determinants (e.g. health
  subsystem affiliation).
- **Official file layouts**: the SS and AT DMR have distinct fixed
  file specifications (positions/fields per worker and per rubrica).
  The exact layouts must be obtained from Segurança Social / AT
  documentation (or sample files) before the exporter can be written.

### Proposed workflow (generation → review → submission)

1. **Generation phase** — a wizard (or scheduled action) per company +
   month creates a `l10n.pt.dmr.declaration` header (state `draft`)
   and one `l10n.pt.dmr.declaration.line` per worker × rubrica,
   populated from the period's validated payslips. Regeneration is
   allowed only while `draft`/`in_review`; once submitted it is locked.
2. **Review phase** — declaration lines are viewable/editable in
   form/list views (manual corrections flagged, e.g. a `manual`
   boolean + chatter tracking). Built-in checks block submission:
   missing NISS/NIF, regime without `l10n_pt_dr_code`, worker without
   payslip, negative rubricas, totals not reconciling with payroll.
3. **Submission phase** — options below; the declaration records the
   channel used, the file produced (attachment), submission timestamp
   and, when known, the validation result. A rectificativa is a new
   declaration referencing the corrected period.

### Implementation options for submission

- **A. File export (baseline, recommended first)** — generate the
  official DMR file(s) for download; the user uploads via Segurança
  Social Direta / Portal das Finanças. Works for all employer sizes,
  no credentials to manage, matches the mandatory channel for 50+
  workers. Blocked only on obtaining the official layout specs.
- **B. API/webservice submission** — research whether Segurança Social
  exposes a DMR webservice for certified software and whether AT
  offers an equivalent; if yes, add a submit action storing
  credentials per company. Uncertain availability — treat as a later
  increment, not a blocker.
- **C. Hybrid** — ship A first; design the declaration model so the
  exporter is one renderer among possible submitters (file now, API
  later). The generation/review phases are identical either way.

### Open questions

- Exact SS and AT DMR file layouts (field positions, rubrica code
  tables) — need official documentation or sample files from the user.
- Whether one file satisfies both SS and AT or two files/models are
  needed (the portal exposes "Preencher AT" / "Preencher SS" variants).
- Which rubrica codes apply to each PT payroll line (meal subsidy
  exempt vs taxable portion, holiday/Christmas pay, overtime...) —
  needs the official code table.
- Whether pre-reforma suspension (worker remits SS directly) appears
  in the DMR at all, and under which code.
- Multi-company: declaration is per employing entity — confirm
  `company_id` scoping covers all cases (single-entity employers are
  the norm; grouped employers need verification).

### Tasks

- [ ] Obtain official DMR file layouts + rubrica code tables (SS and AT)
      — data capture fields are in place; values pending user-provided docs.
- [x] Audit worker fields: NIF is the `vat` field on the work-contact
      partner; birth date, marital status, dependents and union
      affiliation already stored; union dues rate added as
      `l10n.pt.union.l10n_pt_dues_rate`.
- [x] `l10n_pt_dmr_code` on `hr.salary.rule` + editable on the rule
      form alongside `l10n_pt_irs_taxable`; values pending the official
      rubrica code table.
- [ ] `l10n.pt.dmr.declaration` + `.line` models, access, views.
- [ ] Generation wizard/batch from period payslips (draft → in_review).
- [ ] Review checks + manual-correction flagging.
- [ ] File exporter for the official layout(s) + download action.
- [ ] Submission tracking (channel, timestamp, validation result).
- [ ] Rectificativa support (declaration referencing corrected period).
- [ ] Research API/webservice submission feasibility (later increment).

## Contract details

- Money values are floats in euros; the payslip line is the negated, euro-truncated
  retention.
- `parcela_abater` expressions may only use `R` and numeric literals.
- Import is atomic per file.

## Alternatives considered

- **Tables as XML `<record>` data** — rejected: hundreds of rows per year × region ×
  variant is unreadable; CSV mirrors the source.
- **Native Odoo CSV import on lines** — rejected: cannot create parent sets, validate
  contiguity, or load bundled files.
- **`parcela_abater` as structured columns** — rejected: official expressions vary by
  row and year; the expression column is faithful.
- **Region derived from address only** — rejected as sole mechanism: fragile; explicit
  declared field with computed default is auditable.
- **Flat-rate fallback when no table covers the date** — rejected: silent wrong
  withholding is worse than a clear error.
- **Separate IRS module** — rejected (see discussion): table updates are already cheap
  via CSV + wizard; a split adds a dependency edge for no operational benefit. The
  `hr.pt.irs.withholding.*` models + `data/irs/` are self-contained if a split is ever
  needed.

## Open questions

- Jovem `/14` monthly cap is the Despacho n.5-g approximation; confirm against an
  official AT worked example (partial-year exemption accumulation is approximated).
- `l10n_pt_military_disabled` covers pensioners; whether armed- forces disability also
  affects work-income tables needs AT confirmation (n.5-d only references tables X/XI).
- Whether n.5-b `spouse_disabled_parcela` differs per region — resolved: the 2026
  Despachos for continente (233-A), Açores (1179) and Madeira (19 + Retificação 10)
  carry identical n.5 constants (€84.82/€42.41, €135.71, €42.86/€21.43/€34.29,
  €36.38/€18.19); per-set fields still guard future divergence.
- The zip-code fallback split for `l10n_pt_irs_region` needs verification against CTT
  postal tables.
- 2026 mid-year changes (DL 212/2026 retroactive cut, Despacho 12523-A/2026 November
  half-retention): whether to bundle corrected table sets or rely on manual import.

## Tasks

- [x] Move IRS employee fields from `l10n_pt_hr`; add region, disabled dependents,
      pensioner, non-resident, preferred rate, Jovem fields.
- [x] `hr.pt.irs.withholding.table`/`.line` models + access + views.
- [x] `l10n_pt_irs_taxable` Float on `hr.salary.rule` (BASIC = 1.0).
- [x] Retention engine per Despacho n.3/n.5 (brackets, dependent/
      disabled/spouse/pension/forces parcelas, n.5-e rate override, n.5-h 3+ dependents,
      n.6 factor, non-resident 25%, Jovem).
- [x] Bundle 2026 CSVs for continente, Açores and Madeira, generated from the official
      XLSX workbooks (Despachos 233-A/2026, 1179/2026, 19/2026 RAM + Retificação
      10/2026).
- [x] CSV import wizard + bundled loader + post-init hook.
- [x] Tests: payslip integration, preferred rate, non-resident, dependents + 3+
      reduction, disabled-dep factor, disabled spouse, Jovem, missing table, import
      validation, table derivation, region default.
- [x] `scripts/xlsx_to_csv.py`: official AT Excel → bundled CSV converter (`inspect` +
      `convert`), verified against all three 2026 workbooks; `dependent_parcela`,
      `forces_disabled_parcela` and `effective_rate_limit` extracted from the real
      layout; Despacho n.5 constants supplied via `--set-json` (not present in the
      workbooks).
- [x] `effective_rate_limit` transcription (populated from the workbooks).
- [x] Social Security rates configurable on `l10n.pt.ss.regime` (employee TSU,
      employer TSU) + SAT premium on the work insurance policy.
- [ ] SPECS/README regeneration if fragments change.
