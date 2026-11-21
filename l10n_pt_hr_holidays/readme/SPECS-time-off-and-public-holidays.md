# Portuguese time off and public holidays

**Status:** in progress **Date:** 2026-11-21 **Scope:** `l10n_pt_hr_holidays` for Odoo
19 **Related:** [Default Portuguese absence types](SPECS-absence-types.md)

## First slice: annual leave setup

- The addon uses standard Odoo Time Off and installs without Portuguese HR master data
  or payroll.
- Time Off provides the shared Portugal-scoped Annual Leave type (`Férias` in
  Portuguese). Its stable XML ID is `l10n_pt_hr_holidays.leave_type_annual_leave`.
- Employees request full days against an approved allocation. A Time Off Officer
  approves requests. HR enters allocations using Odoo; installation does not grant any
  days or change existing time off types.
- Use the native Odoo public-holiday exclusion. On a Monday-Friday calendar with 10 June
  configured as a public holiday, a request from 8 to 12 June 2026 consumes four days.
  The first slice does not create calendar holidays.
- Company and country visibility follow Odoo's standard Time Off rules. This is not a
  custom cross-company policy.

## Remaining release scope

- Public-holiday generation is outside this addon. The separately installable AGPL addon
  `l10n_pt_hr_holidays_public` is planned for data-driven generation using the OCA
  catalog.
- HR confirms allocations for the first release. The ordinary minimum is 22 working
  days; do not grant that amount indiscriminately. Admission-year entitlement,
  carryover, and other special cases under Articles 237-240 remain manual until
  separately specified. Support conventional Monday-Friday duration counting first;
  verify the Article 238 weekly-rest substitution rule before claiming support for
  nonstandard schedules.
- Provide a printable annual _mapa de férias_ with the start and end dates of planned
  vacation periods. Apply company access boundaries and exclude unrelated absences.
  Verify Article 241 requirements, including the April 15 preparation deadline.
  Establishment grouping belongs in a future optional integration with Portuguese HR
  master data.

Legal reference:
[Código do Trabalho, Articles 234-241](https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2009-34546475).

## Future payroll integration

- Dependency direction is always payroll toward time off, never the reverse. This addon
  owns leave types, allocations, calendars, and approved time-off periods. Payroll owns
  worked-day interpretation, deductions, reporting codes, and vacation subsidy
  calculations.
- Prefer a separate `l10n_pt_payroll_hr_holidays` bridge that depends on both
  `l10n_pt_payroll` and `l10n_pt_hr_holidays` while payroll-only deployments are
  supported. Put the mapping from time off types to payroll treatment and worked-day
  codes in the integration layer. If Portuguese payroll later requires the time-off
  addon for every installation, make `l10n_pt_payroll` depend directly on it instead. Do
  not implement both paths or add either dependency in this slice.
- Keep the optional AGPL public-holiday generator (`l10n_pt_hr_holidays_public`) out of
  the dependencies of this addon, Portuguese payroll, and any LGPL payroll bridge. An
  integration requiring both stacks must be independently installable and depend on
  both.
- Consume approved `hr.leave` periods and native calendar closures. Use the seeded XML
  ID to identify the default vacation type, not its translated label. Keep mappings
  configurable for company-specific types.
- Before enabling the integration, verify with real payslips that paid annual leave
  preserves ordinary pay, unpaid absence produces the intended deduction, calendar
  closures do not become employee absences, and overlapping vacation and holidays are
  not counted twice. OCA `payroll` computes `WORK100` before subtracting calendar leaves
  and can emit `GLOBAL` for calendar closures; verify both lines with the applicable
  `payroll.leaves_positive` setting. Keep vacation subsidy and statutory reporting in
  the payroll specs.

## Alternatives considered

- Extend `l10n_pt_hr` directly: rejected to keep Time Off optional for HR master-data
  users.
- Require OCA `hr_holidays_public` in this addon: rejected to keep the LGPL Time Off and
  payroll dependency chain independent of the optional AGPL generator.

## Tasks

- [x] Add the Time Off addon and the Portuguese annual leave type.
- [x] Add and localize the default Portuguese absence types.
- [x] [Implement and verify the vacation schedule report](SPECS.md).
- [ ] Settle and implement the payroll bridge or direct dependency once payroll adoption
      requirements are known.
