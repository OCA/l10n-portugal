# Annual vacation schedule (mapa de férias)

**Status:** shipped **Scope:** `l10n_pt_hr_holidays` for Odoo 19

## Contract

- A Time Off Administrator selects a year and prints the company-wide PDF for the
  current Portuguese company. Switch companies to print a different company's schedule.
  Enforce these restrictions at print and direct render time without elevated access.
- List approved requests for the seeded Annual Leave type only. Include any request that
  overlaps the selected calendar year, including periods crossing New Year. Display the
  original requested start and end dates, not clipped dates or UTC timestamps. Do not
  include other leave types, reasons, chatter, or entitlement data.
- Show employee name and dates, ordered by employee name and then by date. Show an
  explicit empty message if no approved periods match. This is a live report, not a
  publication workflow or a legal compliance guarantee. Under Article 241(9), the
  employer prepares the schedule by 15 April and displays it at workplaces through 31
  October; HR reviews, prints and posts it.
- Keep the report in LGPL Time Off with no dependency on the optional AGPL generator,
  payroll, or any new scheduling engine. Custom leave types are out of scope in this
  first version.

[Portuguese Labour Code, Article 241](https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2009-34546475).

## Decision record

- Superseded: the original schedule grouped and filtered by the statutory establishment
  effective at the start of each period. Time Off now installs independently of
  Portuguese HR master data. An optional integration with `l10n_pt_hr` can restore
  establishment grouping later without changing the base dependency chain.

## Tasks

- [x] Verify PDF output, source dates, company scoping and access.
- [x] Verify Time Off and the optional generator together without duplicate holiday
      data.
