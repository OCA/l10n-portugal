# Work Time Agreement

**Status:** implemented (verified locally) **Date:** 2026-11-21 **Scope:** `l10n_pt_hr`
contract configuration and `l10n_pt_payroll` settings and hourly remuneration.
**Related:** [Overtime](overtime.md).

## Contract and configuration

- Show a **Portugal: Work Time Agreement** section in Payroll / Contract Overview. Keep
  the existing **Working Hours** calendar editable and unchanged. It continues to drive
  operational scheduling and leave.
- Store the arrangement, contractual weekly hours (PNT), and full-time reference hours
  on `hr.version`. The employee form edits the selected version, not a second set of
  employee fields.
- Provide a configurable arrangement list with Fixed Schedule, Flexible Schedule, and
  Exempt Schedule (IHT). HR managers can add and archive options. Archived options
  remain readable on existing versions. Choosing a type does not change the calendar.
  Remote and hybrid location arrangements are out of scope.
- For a Portuguese contract with entered PNT and no explicit reference, copy the
  selected Collective Contract's positive full-time reference, or the employee company's
  default if none is configured. The company default is 40 hours and editable in Payroll
  / Settings. HR can override the contract reference. Later edits to calendars,
  collective-contract defaults, or company settings do not rewrite a saved reference. Do
  not infer a contractual PNT from a calendar.
- Show the company default in a **Portugal** block in Payroll / Settings. Hide the whole
  block unless the active settings company is Portuguese.
- A read-only **Part-time** flag is true only when both hours are positive and PNT is
  below the reference, comparing to hundredths of an hour. Keep unset values valid for
  existing contracts. Negative hours are invalid; the company default must be positive.

## Payroll

- Compute statutory hourly remuneration as
  `monthly remuneration * 12 / (52 * weekly PNT)`
  ([Labour Code, article 271](https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2009-34546475)).
  Callers supply the monthly remuneration basis and use the version effective for the
  work. This feature does not change existing salary rules, decide which supplements
  enter the basis, or calculate employer cost.
- A missing PNT raises a clear error only when the hourly helper is called. The
  full-time reference and actual hours worked never enter the formula. Do not round in
  the helper.

## Acceptance

- A new 35-hour version under a collective contract with a 35-hour reference is not
  part-time; a 35-hour version with a 40-hour reference is part-time. Explicit reference
  overrides win. For missing or above-reference hours, the checkbox stays unchecked;
  that does not establish full-time status.
- If there is no collective reference, the employee company's default is used even when
  another company is active. Changes to defaults and shared calendars leave prior
  versions intact.
- A 20-hour version and a monthly remuneration of 1,000 yield approximately 11.53846 per
  hour. A 40-hour historical version uses 40, not the currently selected version's 20.
  No PNT produces an actionable error.

## Tasks

- [x] Add versioned agreement fields, configuration and employee view.
- [x] Add Payroll settings and the statutory rate helper.
- [x] Verify contract defaults, historical values, classification and rate calculation.

## Decision Log

- 2026-11-21: Supersede the dedicated Work Time Agreement warnings for missing or
  above-reference hours. Revisit these cases as part of a future shared HR/payroll
  alerts feature. Keep the missing-PNT error when an hourly rate is requested.
