# Monthly IRS withholding

**Status:** in progress

**Scope:** Ordinary Portuguese employment income on multiple payslips. **Related:**
[DMR-AT](dmr-at.md), [Leaves and Absences](leaves-and-absences.md),
[Overtime](overtime.md).

## Requirements

- Apply the ordinary withholding calculation to all ordinary taxable income paid by the
  same employer to the same employee in the month, across contract versions. Use Payment
  Date, falling back to the period end when blank. Use the current payslip's applicable
  withholding table and determinants when recalculating the monthly liability.
- On each later payslip, book only the difference between the rounded month-to-date
  withholding and the actual IRS already withheld for the same income. Do not rewrite
  previous payslips. An earlier payslip with zero IRS still contributes its taxable
  income.
- Use finalized slips as the source for earlier payments while payment tracking is
  unavailable. Exclude drafts, slips in verification and canceled slips. Keep OCA's
  confirmation workflow. Reject a payment date before the last finalized IRS payment in
  the same month. If either slip lacks a Payment Date, require explicit dates whenever
  there is another finalized IRS slip in that month. Allow equal dates when confirmed
  separately. Confirm at most one IRS payslip per employee, employer and month in each
  batch; concurrent requests are not supported.
- Read the earlier slips' recorded taxable amounts and amounts withheld, not today's
  salary-rule setup. Older slips without those snapshots need a verified carry-in rather
  than treating their taxable income as zero.
- Apply monthly reliefs only once across the aggregate: IRS Jovem uses cumulative
  income, and the per-payment single-payer inputs must not together exceed the
  applicable monthly allowance. Explain the monthly base, the recomputed withholding and
  the prior withholding on the new IRS line.
- Keep income subject to autonomous withholding outside this calculation: holiday and
  Christmas subsidies, overtime and prior-year pay. Current-year arrears relating to a
  different month also need their own handling. See CIRS Articles 99-C(4)-(7) and
  99-E(2).

## Acceptance cases

- Two ordinary payments of EUR 800 and EUR 700. If the applicable table yields zero
  withholding on EUR 800 and EUR 168 on EUR 1,500, the second slip withholds EUR 168,
  even if EUR 700 in isolation would withhold zero.
- If EUR 80 was previously withheld and the cumulative liability is EUR 168, withhold
  EUR 88 on the later slip. Recomputing that draft does not count its own lines or
  modify the earlier payslip.
- An earlier draft or canceled slip, a different employer or month, and an autonomous
  subsidy do not contribute to the ordinary calculation.
- Multiple payments on the same date can be confirmed separately, not together. When
  Payment Date crosses a month boundary, it controls both table selection and grouping,
  regardless of the period end.

## Initial implementation boundaries

- Block backdating within a month with a later finalized IRS slip, months with a
  finalized IRS reversal, and a recalculated amount below the amount already withheld.
  The correction workflow remains manual.
- Snapshot the taxable base before relief (`PT_IRS_BASE`) and the single-payer allowance
  actually used (`PT_IRS_ALLOWANCE`) on hidden salary-rule lines, using native Amount
  and Total at 100%. Keep the incremental withholding on `IRS`. Block earlier finalized
  IRS lines without both helper lines; do not infer their taxable base or recalculate
  final payslips.
- The non-resident input still takes the operator-verified remaining share of the
  statutory cap. Aggregate only the amounts actually used; do not derive the regional
  cap automatically.
- The starter structure calculates only ordinary withholding. Rules configured as
  IRS-taxable must not include autonomous income until separate withholding rules
  support it.
