Assign the "PT Payroll" salary structure to employee contracts
(Employees → employee → Payroll Information → Salary Structure),
or use it as the parent structure for company specific structures.

When the database is created with demo data enabled, the PT Company
employees from `l10n_pt_hr` are automatically assigned this structure.
Create a payslip for one of them and click "Compute Sheet" to see the
Portuguese payslip lines.

Christmas subsidy (Subsídio de Natal)
-------------------------------------

Payroll does not compute the subsidy entitlement. Verify the employee's
right to the Christmas subsidy yourself — including base salary and
length-of-service (diuturnidades) increments — and enter the verified
annual entitlement (after any proration) in **Subsídio de Natal**
(`PT_NATAL`) under *Other Inputs*. Use the regular structure or **PT Payroll
- Christmas Subsidy** for a standalone payment. Check for
subsidies already paid outside payroll and for suspensions or
settlements that reduce the amount due.

The payslip shows the annual entitlement and a separate negative correction
for earlier finalized subsidy payments from this employer in the same year.
Only the difference is payable. An already-paid entitlement nets to zero.
Any excess already paid requires manual review. Set an explicit **Payment
Date** inside the payslip period year, normally by December 15. Confirm
payslips sequentially with **Compute on Confirm** enabled, or recompute each
one immediately before confirming it.
For non-resident workers
with a single-payer declaration on file, and for pensioners, the
withholding must be reviewed manually before paying.

Christmas subsidy in duodécimos (Subsídio de Natal em Duodécimos)
----------------------------------------------------------------------

To pay the subsidy monthly instead of one lump sum, enter the reviewed
annual entitlement in **Subsídio de Natal em Duodécimos - Direito Anual**
(`PT_NATAL_MONTHLY`) under *Other Inputs* on each regular payslip — do not
also enter the lump-sum **Subsídio de Natal** input. Each payslip pays one
twelfth of the entitlement for its Payment Date month, distributing
residual cents so the yearly total matches, capped at the unpaid annual
balance. Missed months are not automatically paid later. Set an explicit
**Payment Date** inside the payslip period year and confirm slips in date
order. To settle any remaining balance early, enter the regular
**Subsídio de Natal** input with the full annual entitlement on a standalone
or regular payslip; it
subtracts the installments already paid.

Holiday subsidy (Subsídio de Férias)
-------------------------------------

The holiday subsidy is separate from paid annual leave: it is extra
remuneration paid before the vacation starts. Verify the employee's
entitlement yourself — base remuneration plus the retributive benefits
tied to how the work is performed — and enter the reviewed gross annual
amount in **Subsídio de Férias - Direito Anual** (`PT_FERIAS`) under
*Other Inputs*. Use the regular structure or **PT Payroll - Holiday
Subsidy** for a standalone payment.

When the subsidy is paid in parts — for example EUR 700 before the
first vacation block and the remaining EUR 700 before a later one —
enter the cumulative amount due through this payment in **Subsídio de
Férias - Total a Pagar até à Data** (`PT_FERIAS_TARGET`): with a EUR
1,400 annual entitlement, a target of 700 pays EUR 700, and a later
blank or 1,400 target pays only the remaining EUR 700. Repeating an
already-paid target pays nothing. Leave the target empty to settle the
full remaining entitlement.

To pay the subsidy monthly instead, enter the reviewed annual
entitlement in **Subsídio de Férias em Duodécimos - Direito Anual**
(`PT_FERIAS_MONTHLY`) under *Other Inputs* on each regular payslip —
never together with the manual holiday inputs, and only under a written
agreement. Each payslip pays one twelfth of the entitlement for its
Payment Date month, distributing residual cents so the yearly total
matches, capped at the unpaid annual balance; missed months are not
caught up later. Holiday Social Security is calculated separately on
the installment actually paid, at the contract regime rates. Set an
explicit **Payment Date** inside the payslip period year and confirm
payslips sequentially with **Compute on Confirm** enabled, or recompute
each one immediately before confirming it. Prior-year payments, external
payments, reversals and the pensioner or non-resident single-payer
cases require manual review.
