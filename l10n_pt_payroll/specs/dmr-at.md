# IRS DMR-AT file generation

- **Status:** draft; official upload layout not verified
- **Date:** 2026-11-21
- **Scope:** `l10n_pt_payroll`, resident Category A income, file export for manual
  upload to Portal das Financas
- **Related:** [previous reporting draft](../readme/SPECS.md), [overtime](overtime.md),
  [leaves and absences](leaves-and-absences.md)

## Context

DMR-AT reports Category A income paid or made available to Portuguese tax residents,
including reportable exempt and non-taxable amounts and amounts with zero withholding.
It also reports actual IRS withheld, mandatory employee contributions and union dues. SS
DR/SCC, Modelo 30 and direct submission to AT are out of scope. The reporting period is
the month of payment or availability, not the worked month.

- [Portaria 33/2024](https://diariodarepublica.pt/dr/detalhe/portaria/33-2024-839799721):
  official form and submission rules.
- [Portaria 69/2026/1](https://diariodarepublica.pt/dr/detalhe/portaria/69-2026-1047287417)
  and
  [AT circular 20290/2026](https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/legislacao/instrucoes_administrativas/Documents/Oficio-circulado-20290-2026.pdf):
  instructions and income codes effective 2026-01-01.
- [Portal das Financas DMR](https://sitfiscal.portaldasfinancas.gov.pt/geral/servicosRelacionados?appName=oadmrsv):
  upload and offline validator. The form is not the upload format.

## Salary-rule configuration

On the Portugal tab of `hr.salary.rule` add `l10n_pt_dmr_at_role` with `income`,
`withholding`, `contribution`, `union_dues`, and `ignore`. Leave the default unset so a
nonzero, unclassified line in a PT structure is an error, not an implicit exclusion.
Reuse `l10n_pt_dmr_code` as the AT income code for `income` only. Validate against a
versioned AT catalog with code, label, validity and Quadro 4 classification rules. Keep
SS nature codes separate. Require the receiving entity NIPC for a `contribution` rule,
with one recipient per rule; use separate rules for different recipients. A deduction
never has its own income code. Keep `l10n_pt_irs_taxable` for withholding calculation
only. Neither a zero taxable share nor zero IRS withholding excludes a reportable
earning.

| Payroll line                                                             | DMR-AT configuration and result                                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BASIC`, ordinary overtime, commissions and ordinary taxable supplements | `income`, `A` for ordinary treatment. Apply a special code only when the actual income qualifies.                                                                                                                                                                                                                                                                                                                            |
| Holiday and Christmas subsidy, including installments                    | Separate payroll rules, `income`, `A3` and `A4` respectively for ordinary treatment. Keep them distinct even if paid with salary.                                                                                                                                                                                                                                                                                            |
| Meal allowance (`SA`)                                                    | Replace the mixed line with two payroll results: `SA_NONTAXABLE` (`income`, `A21`, taxable share 0) and `SA_TAXABLE` (`income`, `A`, taxable share 1 under ordinary treatment). Payroll computes the limit by payment method, eligible days and effective date. The two amounts must add back to the allowance. A legacy mixed `SA` line requires an evidenced split before export; a configured percentage is not evidence. |
| IRS Jovem                                                                | For qualifying income, resolve the effective code to `A68` from the payment's documented regime. For current-year income put the full qualifying amount, including the exempt portion and eligible holiday/Christmas subsidies, on `A68`; do not also emit those amounts under `A`, `A3` or `A4`. Do not infer eligibility from age or the withholding amount.                                                               |
| `IRS`, `SS`, statutory health, union dues                                | `withholding`, `contribution` (with SS NIPC), `contribution` (with subsystem NIPC), and `union_dues`, respectively. Report actual employee deductions from payroll results, not percentages recomputed by the exporter.                                                                                                                                                                                                      |
| `GROSS`, `NET`, `SS_COMP`, `SAT_COMP`, other totals and employer costs   | Explicit `ignore`. Do not count aggregates or employer charges as employee income or contributions.                                                                                                                                                                                                                                                                                                                          |

Seed the roles for known shipped rules. Do not seed existing `SA` as entirely `A21`, or
relabel arbitrary pre-existing custom codes as AT codes. Make unverified legacy mappings
visible for payroll review. The exporter does not implement withholding, eligibility, or
exemption calculations. Where payroll does not yet provide the necessary classification,
split, or attribution, require documented review data or block export.

### Salary-rule configuration milestone (2026-11-21)

This milestone adds rule configuration only. Seed the existing base salary as AT `A` /
SS `P`, employee IRS as withholding, employee SS as a contribution, and payroll totals
and employer costs as ignored. Leave the mixed meal rule unclassified until the company
can document and split the paid amounts. Do not seed a universal receiving NIPC: it can
vary by employer location. The declaration builder must reject missing recipient and
code data; the setup fields may remain blank before export exists.

SS uses a separate proposed `l10n_pt_ss_nature_code` and a contribution-base treatment
of Include, Exclude, or unset (preserve legacy BASIC-category behavior). Apply the
employee and employer rates to the same base. An explicitly included addition
contributes even if not taxable for IRS. An explicitly excluded earning does not
contribute even if taxable for IRS or part of the BASIC category. Rules with distinct
treatment must yield distinct payroll amounts; do not infer a legal split from the IRS
taxable share. This is not a full statutory SS calculation or a declaration exporter.
The DR and SCC renderers will validate their own permitted codes. Configure affected
earnings before the employee SS rule so both contributions use the same base.

## Generation and review

1. **Select sources.** Create a draft for one employing company and declaration month.
   Use finalized Portuguese payslips paid or made available in that month, including
   off-cycle payments. A confirmed fiscal payment/availability date is required. Core
   `hr.payslip.paid_date` is a candidate, not proof: marking a slip paid sets it to
   today's date. Never fall back to the payslip period, confirmation date, or the
   generation date. Unpaid slips are not included; paid slips with an unresolved date
   and confirmed partial/cross-month payments without an evidenced split must be
   resolved before export. Scope by allowed company and avoid including the same
   payment/line more than once.
2. **Normalize.** Read posted payslip line totals and their rule IDs, not `NET`,
   category totals, or a new payroll calculation. Resolve the recipient NIF
   (`employee_id.work_contact_id.vat` convention), fiscal residence at payment,
   income-attribution year, and place of work for each income amount. Use `C`, `RA`,
   `RM` or `E` for the income location, never the withholding-table region or SS
   establishment. Exclude known non-residents with an auditable reason; block on unknown
   residence. When work spans locations or income relates to several years, use
   evidenced splits. Stop on missing facts rather than applying current employee data to
   historical payments without review.
3. **Attribute deductions.** Use the actual IRS, mandatory employee contribution and
   union amounts from classified source lines. Convert ordinary negative payroll
   deductions to positive report values; do not apply `abs()` to corrections. Attach
   each deduction to the income row(s) it relates to. Auto-assign only when one eligible
   target is unambiguous. For multiple eligible rows require explicit payroll allocation
   or a reviewed split tied to the source deduction. No default gross-proportional
   allocation and no copying the same deduction to multiple rows. Reconcile each source
   amount to its allocations to the cent, preserving each contribution recipient NIPC.
4. **Project the form.** Group Quadro 5 by
   `(worker NIF, AT income code, income location, attribution year)` where contribution
   recipient representation permits, retaining the recipient set with amounts up to the
   supported layout. For prior years use field 02 (amount and year); for the declaration
   year use field 03. Do not coalesce current and prior years, even for the same
   worker/code/location. Fields 06, 07 and 08 carry IRS, mandatory contributions with
   recipient NIPCs, and union dues. Derive Quadro 4 totals by AT category from Quadro 5
   using the applicable instructions for mixed-treatment codes. Validate company NIF,
   tax office, period and applicable Quadro 6/7 metadata independently of the transport
   layout.
5. **Review and freeze.** Show included and excluded payments, source lines, regrouped
   rows and reconciled totals. Keep decimal/cents arithmetic in the report engine; never
   recompute IRS from the taxable share. Block missing or invalid mappings, duplicate
   sources, missing identifiers, unreconciled splits, unsupported signs, and unsupported
   form cases. Persist the reviewed source facts, adjustments with reason, projected
   rows, period and profile version in an access-controlled declaration snapshot.
   Restrict access and downloads to authorized payroll users in the declaring company. A
   replacement is a separate, linked snapshot for the original month, with complete
   corrected data and applicable Quadro 6 reason/date; do not write over the prior
   export or generate a delta file. Unsupported correction cases must be blocked and
   identified to the reviewer.

## File renderer

The projection and file renderer are separate. A versioned `models.AbstractModel`
renderer takes only the frozen declaration projection and an official file profile, and
returns bytes and an upload filename. It does not query current payroll or company
records and it does not submit to AT. Use an explicit profile for the selected period
and filing case; no default profile for an unknown period. Re-export of the same
snapshot with the same profile is byte-identical. Store the exact file as a private
attachment and keep export state separate from AT submission/acceptance; a download is
not a filing receipt.

**Release gate:** obtain the current _Suporte Informatico DMR-AT_ layout and a sanitized
validator-accepted fixture. Confirm record/schema version, field ordering, widths or
separators, encoding, number/sign/rounding conventions, blank and zero rules, ordering,
filename and correction handling from the package and validator. Confirm Quadro 4
handling of mixed-treatment codes and Quadro 5 representation when multiple contribution
recipients are present. Do not infer text versus XML, borrow the SS layout, truncate
data, or make an upload file available before verification. A clearly labeled review
preview can ship independently.

## Acceptance scenarios

- December work paid in January is included in January only. Prior-year arrears occupy
  their own field-02 row; January earnings use field 03. Off-cycle payments are included
  once, and another company is excluded.
- An ordinary payslip with salary, holiday pay, Christmas pay and mixed meal allowance
  projects `A`, `A3`, `A4` and `A21` as applicable. Employer costs and payroll subtotals
  are not exported. An eligible IRS Jovem payment reports the full qualifying amount
  once under `A68`, including the exempt part.
- Employee IRS, SS, statutory health and union dues reconcile exactly even when there
  are several income rows. An ambiguous deduction or a missing income code prevents
  download and identifies the source line.
- Known non-residents are not reported by DMR-AT. Missing residence, work location,
  payment timing or unsupported corrections cannot silently produce an upload file.
- Edits to salary rules after freezing do not change a prior upload. An original and a
  supported replacement for the same month are separate files and both pass the AT
  validator.

## Alternatives considered

- A shared AT/SS code and combined export: rejected because the authorities use
  different code sets, data and submission workflows.
- Infer classification from payroll categories or recompute tax at export: rejected
  because similar net amounts can have different legal reporting and allocations.
- Ship an assumed format from the form or a vendor example: rejected because the Portal
  validates a separate versioned transport contract.

## Tasks

- [ ] Obtain the AT package, confirm the open profile rules, and validate sanitized
      original and replacement fixtures.
- [x] Add rule configuration and baseline seeds, with a separate configurable SS base.
- [ ] Implement the versioned AT code catalog and split/attribution inputs.
- [ ] Implement the monthly projector, review and immutable declaration snapshots.
- [ ] Add the verified renderer, private downloads and feature-level acceptance
      coverage.
