# Portuguese public holiday generation

**Status:** shipped **Date:** 2026-11-21 **Scope:** `l10n_pt_hr_holidays_public` for
Odoo 19

## Dependency boundary

- `l10n_pt_hr_holidays_public` depends on `hr_holidays_public`. Only the optional
  generation layer uses the OCA holiday catalog. `calendar_public_holiday` is a direct
  dependency because the implementation extends its line model.
- `l10n_pt_hr_holidays` stays LGPL-3 and owns Portuguese leave types, allocations, and
  the vacation schedule. It does not depend on the generator, `hr_holidays_public`, or
  `calendar_public_holiday`.
- `l10n_pt_payroll` can later depend on `l10n_pt_hr_holidays`, or connect through an
  LGPL bridge if the relationship remains optional. Neither can depend directly or
  transitively on the AGPL holiday stack. If an integration needs both payroll and the
  OCA catalog, it belongs in a separately installable addon that depends on both, never
  the reverse.

## Generation contract

- Seed Portuguese holiday rules as editable data rather than a Python list. A rule can
  be a fixed month/day or a signed offset from Western Easter Sunday. Keep one-off dated
  entries out of the carry-forward flow.
- Apply rules to the target year. Previous-year reuse must carry forward rules, not the
  dates observed last year. Keep annual substitutions local to the selected year.
- This addon generates Portuguese nationwide entries in the OCA catalog and does not
  create native work-calendar closures. The generated records apply across companies
  according to OCA country/state matching. Regional and municipal dates remain manual,
  as do company-only closures. Never enter the same holiday in both OCA and native Odoo.
- Dated entries, including previously generated ones, are never rewritten. Review the
  selected year after editing a rule that was already used.
- Preview changes before applying. Leave existing manual records alone, avoid duplicates
  on rerun, and represent multiple holidays sharing one date without losing their names.
  Keep existing Portuguese leave workflow independent of whether this addon is
  installed.

## Acceptance criteria

- On 2026 generation, add 13 mandatory Portuguese dates (including Good Friday on 3
  April, Easter on 5 April, and Corpus Christi on 4 June). A second apply makes no
  changes. When Easter Sunday and Freedom Day share 25 April 2038, keep both names in
  one line.
- Optional Carnival Tuesday is 47 days before Western Easter. If selected in 2026,
  previous-year reuse includes it on 9 February 2027 instead of copying 17 February.
  Only previously linked active optional rules from nationwide Portugal lines carry
  forward; ignore unlinked one-offs. Manual optional selections supplement
  carry-forward.
- Preview indicates to add, already covered, or regional overlap to review. Treat an
  existing nationwide Portuguese or country-independent date as covered. Leave regional
  and manual entries unchanged. Only Time Off Administrators can generate or edit rules;
  use the regular OCA ACLs without escalation.
- Leave older years alone. The shipped rule set represents the modern calendar, and the
  wizard only generates target years 2017-2099. An optional February 29 rule has no
  occurrence in a non-leap year.
- Generated records are nationwide even when the caller supplies a regional default in
  its context.

Legal reference:
[Código do Trabalho, Articles 234-235](https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2009-34546475).

## Alternatives considered

- Keep the hardcoded list in the LGPL Time Off module: superseded by data-backed
  recurrence and the decision to isolate OCA holiday generation.
- Make Portuguese Payroll depend on `hr_holidays_public`: rejected because localized
  payroll and leave workflows must install without the AGPL holiday stack.

## Tasks

- [x] Decide the dependency direction and addon split.
- [x] Resolve company-calendar scoping against the OCA country/state model.
- [x] Implement the optional generator, its seed rules, and tests for carry-forward,
      one-offs, and collisions.
- [x] Retire the wizard prototype from the LGPL addon (done in the base commit) and
      verify both install paths independently.
