# Overtime (trabalho suplementar) — spec

**Status:** draft **Date:** 2026-11-20 **Scope:** `l10n_pt_payroll` — capture,
computation rules, annual threshold tracking **Related:** `readme/SPECS.md` (DMR section
— overtime earnings need their own rendimento codes), `specs/leaves-and-absences.md`

## Context

Portuguese law pays overtime at statutory premium rates that depend on two variables:
the day type (normal working day vs weekly rest day / public holiday) and the employee's
**cumulative annual overtime** (100-hour threshold, CT art. 268). Nothing in OCA
`payroll` computes this: there is no attendance integration in the community edition, so
overtime hours must be captured per payslip and priced by rules.

## Legal requirements (CT art. 226–229, 268)

Premiums are added to the hourly rate (`retribuição horária`):

| Situation                                             | ≤ 100 h/year                                | > 100 h/year                |
| ----------------------------------------------------- | ------------------------------------------- | --------------------------- |
| Normal working day                                    | +25% first hour/fraction, +37.5% subsequent | +50% first, +75% subsequent |
| Weekly rest day (obrigatório/complementar) or holiday | +50% every hour                             | +100% every hour            |

Additional rules:

- Work on a rest day/holiday also grants **one paid compensatory rest day** within the
  following 3 working days (art. 229) — payment and rest are cumulative rights, not
  alternatives, unless the worker opts for payment instead where the law allows.
- Overtime is only payable when pre-authorized or unavoidable (art. 268 n.4).
- Annual limits exist (verify current caps — art. 226/227 framework; historically 200
  h/year general, higher for SMEs/micro).
- Night-work supplements and shift premiums are separate remuneration — out of scope
  here unless they interact with the hourly-rate base.

## Spec

### Data capture

Overtime hours must reach the payslip with two attributes: quantity and day type.
Options:

- **A. Payslip worked-days lines** — extend the worked-days mechanism with OT codes
  (e.g. `OT_DIA`, `OT_REPOUSO`) carrying hours; populated manually or by a wizard from
  an external source.
- **B. Payslip input lines** — `hr.payslip.input` entries per OT type; simplest, already
  supported by the engine.
- **C. Dedicated overtime object** — `l10n.pt.overtime` records (employee, date, hours,
  day type) rolled up into the payslip; enables the annual counter and compensatory-rest
  tracking, at the cost of a new model + views.

Recommendation: **C for tracking + B/A for payslip input** — the annual 100 h threshold
and compensatory rest cannot be computed from flat payslip inputs alone; they need
per-day records. Revisit after checking how other OCA payroll localizations model OT.

### Hourly rate base

PT convention for `retribuição horária`: monthly base remuneration ÷ (weekly working
hours × 52 ÷ 12). For 40 h/week → ÷173.33. Confirm whether base includes
seniority/diuturnidades and which supplements count — flag for validation against
official guidance or a CCT.

### Payroll rules

- OT premium rules per band: `OT1` (≤100 h, day), `OT2` (>100 h, day), `OT3` (≤100 h,
  rest/holiday), `OT4` (>100 h, rest/holiday) — the band is decided by the employee's
  YTD overtime at the time of the payslip.
- OT amounts are category-A remuneration: included in the SS/IRS bases (check interplay
  with `l10n_pt_irs_taxable` and the SS regime rate base — OT likely joins
  `categories.BASIC` or a new taxable category).
- Compensatory rest days, when taken, are paid leave — they need a leave-type treatment
  (see leaves spec) or a dedicated flag.

### Annual counter

A per-employee, per-calendar-year accumulator of overtime hours, reset each January,
driving the 100 h threshold. Stored where? Options: computed from overtime records
(preferred — auditable) vs a manual counter field.

## Open questions

- Exact current annual caps and weekly rest-day definition edge cases (trabalho por
  turnos, domíngos normais).
- Does the company want compensatory rest tracked, or is payment-only acceptable for the
  target customers?
- Interaction with `l10n.pt.work.insurance` premium base — is OT insurable remuneration?
- DMR rendimento codes for each OT band (needed for `l10n_pt_dmr_code` seeding).

## Tasks

- [ ] Research how other OCA payroll localizations model overtime (check l10n-\* repos
      for precedent)
- [ ] Decide capture model (A/B/C) and where OT records live
- [ ] Define hourly-rate formula and confirm the remuneration base
- [ ] Implement annual YTD counter + threshold logic
- [ ] Implement the four premium bands as salary rules
- [ ] Compensatory-rest tracking (if in scope)
- [ ] Tests: each band boundary (99.5 h vs 100.5 h), rest-day vs working-day, year
      rollover, partial hours/fractions
