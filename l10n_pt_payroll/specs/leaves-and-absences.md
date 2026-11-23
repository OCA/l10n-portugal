# Leave types and absences — spec

**Status:** draft **Date:** 2026-11-20 **Scope:** `l10n_pt_payroll` (rules, leave-type
mapping), possibly `l10n_pt_hr` (leave-type configuration fields) **Related:**
`readme/SPECS.md` (DMR section — absence rubricas feed the declaration),
`specs/overtime.md`

## Context

Portuguese payroll must handle the full leave/absence landscape: annual leave (férias),
sick leave (baixa), parental leave, justified and unjustified absences, and the two
extra monthly payments (subsídio de férias, subsídio de Natal). Today the PT structure
pays a flat monthly base and knows nothing about days not worked, so every absence
either overpays or is invisible.

OCA `payroll` already aggregates `hr.leave` records into payslip _worked days_ lines:
`_compute_leave_days` groups leaves by holiday status and emits one
`hr.payslip.worked_days` line per type, coded from
`hr.leave.type.work_entry_type_id.code` (fallback `GLOBAL`). The sign of the amounts
depends on the `payroll.leaves_positive` config parameter (default: subtract). Salary
rules can read these lines as `payslip.worked_days.<CODE>`.

## Spec

### Leave-type → payroll mapping

Each `hr.leave.type` used in Portugal gets a payroll treatment. The mapping must be
configurable per leave type, not hardcoded per record.

Proposed field on `hr.leave.type` (new small extension, in `l10n_pt_payroll` or
`l10n_pt_hr` — decide):

- `l10n_pt_payroll_treatment` selection:
  - `none` — no payroll effect (default)
  - `unpaid` — absence without pay: deducts proportional remuneration
  - `paid` — absence with pay: no deduction (vacation, paid justified absences)
  - `external` — subsidized by Segurança Social: no employer pay, but the absence must
    still be declared (DMR absence rubrica)
- `l10n_pt_dmr_absence_code` — official DMR absence/motivo code, feeds the declaration
  like `l10n_pt_dmr_code` does for earnings.

Seed the standard PT leave types with their treatment:

| Leave type                                                  | Treatment                              | Basis                                                                                    |
| ----------------------------------------------------------- | -------------------------------------- | ---------------------------------------------------------------------------------------- |
| Férias (annual leave)                                       | `paid`                                 | CT art. 237 — férias are paid time off                                                   |
| Baixa médica (sick)                                         | `external` days 4+ / `unpaid` days 1–3 | CT art. 255 n.2; DL 28/2004 art. 21 — 3-day waiting period unpaid, SS subsidy from day 4 |
| Licença parental                                            | `external`                             | Subsídio parental paid by SS, not employer                                               |
| Falta injustificada                                         | `unpaid`                               | Loss of proportional pay                                                                 |
| Falta justificada (paid cases: casamento, nascimento, luto) | `paid`                                 | CT art. 249–250                                                                          |
| Autodeclaração de doença                                    | `unpaid`                               | Justified but unpaid (SNS 24, max 3 days ×2/year)                                        |

The sick-leave 3-day waiting period cannot be expressed as a single leave-type treatment
— see "Open questions".

### Payslip computation

- **Unpaid absences** produce a deduction rule: proportional loss of the period's
  remuneration. Base = the remuneration the employee would have earned (basic +
  seniority + recurring supplements), divided by the period's payable days/hours.
- **Paid and external absences** produce no deduction. External ones still emit a
  declaration-facing record (see DMR spec).
- Vacation days themselves do not change the monthly pay (férias are paid leave); only
  the _subsídio de férias_ is extra — see below.

### Subsídio de férias and subsídio de Natal

Both are separate remuneration payments with strict deadlines:

- **Subsídio de Natal** — one month of base remuneration + seniority (diuturnidades),
  paid by 15 December (CT art. 263). Proportional in the year of admission, cessation,
  or suspension.
- **Subsídio de férias** — base remuneration plus retributive benefits tied to the
  specific way work is performed (shift/night-work supplements), corresponding to the
  minimum vacation duration; paid before the vacation starts, or proportionally per
  vacation block, unless otherwise agreed in writing (CT art. 264).

Implementation options (decision pending):

- **A. Bonus rules on regular payslips** — duodécimos-style monthly installments (1/12
  each month) controlled by a contract/employee flag "subsídio de férias/natal em
  duodécimos". Simple, matches the common practice for Natal (subject to legal and
  contractual verification) and férias (confirm whether the applicable written agreement
  permits this schedule).
- **B. Dedicated bonus payslips** — generated when a `hr.leave` of type férias starts
  (férias subsidy) or in November/December (Natal). More faithful to the legal
  deadlines; needs payslip-run support for ad-hoc bonus runs.
- **C. Hybrid** — monthly installments by default; a wizard generates the
  complementary/adjustment payslip for proportional cases (admission, termination,
  mid-year vacation).

> **2026-11-23:** Payroll now supports reviewed current-year holiday subsidy amounts on
> regular or holiday-only payslips, with cumulative targets for split leave. Automatic
> entitlement, scheduling from Time Off, and cross-year settlements are still pending.

**Acceptance criteria before release**

- Record Natal and Férias as distinct earnings, separate from ordinary monthly
  remuneration, paid vacation, and each other. Confirm the eligible components and any
  applicable collective-agreement overrides before implementing the bases.
- Track entitlement, amounts already paid and outstanding amounts separately. Cover
  mid-year hires, termination and qualifying suspension. For Férias, cover split leave
  blocks and the final settlement independently of Natal.
- Support statutory payment timing first. Treat duodécimos as payment installments, not
  as entitlement accrual. Keep them opt-in only after verifying the applicable legal and
  contractual conditions for each subsidy.
- Calculate IRS withholding separately for each subsidy under the applicable rules
  (including installment treatment if supported). Verify Social Security inclusion and
  DMR-AT/SS classification without combining their earning lines.
- Check a full-year entitlement, a prorated hire, split vacation, and a termination with
  prior payments. Re-running payroll must not pay an installment twice.

## Open questions

- Sick leave: days 1–3 unpaid, 4+ external — needs either two leave types (baixa <4d /
  baixa ≥4d) or a computed split on the leave line. Which is cleaner for users?
- Do collective agreements (CCTs) in scope pay the first 3 sick days? If yes, the
  treatment needs a per-employee/company override.
- Parental leave: employer keeps SS declaration obligations (DMR absence code) — confirm
  the exact DMR absence codes before implementing `l10n_pt_dmr_absence_code` values.
- Férias planning: does `hr.leave` carry the gozado period blocks needed for
  proportional subsídio de férias, or do we need a dedicated férias-planning object?
- Are public holidays (feriados) handled? They are not `hr.leave`; check whether payroll
  already excludes them via the work calendar.

## Tasks

- [ ] Decide where the leave-type payroll fields live (`l10n_pt_hr` vs
      `l10n_pt_payroll`)
- [ ] Add `l10n_pt_payroll_treatment` + `l10n_pt_dmr_absence_code` to `hr.leave.type`,
      views, seeds for standard PT leave types
- [ ] Unpaid-absence deduction rule (proportional to payable days/hours), category DED,
      DMR-visible
- [ ] Verify worked-days sign convention (`payroll.leaves_positive`) and pick codes per
      leave type
- [ ] Choose subsídio de férias/Natal approach (A/B/C) and spec the rules + proportional
      logic
- [ ] Tests: vacation month unchanged, unpaid sick days deduct, parental leave no-pay +
      declaration line, subsídio amounts and deadlines
