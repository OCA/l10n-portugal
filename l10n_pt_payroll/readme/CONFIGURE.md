IRS withholding determinants
----------------------------

The IRS retention inputs live on each employee version (Employees →
employee → *Payroll Information* tab, right after *Disability Degree*):
family status, dependents, disabled dependents (with factor), disabled
spouse, region, pensioner, armed-forces disability, non-resident flag,
preferred rate and IRS Jovem. The region defaults from the employee's
address (Açores/Madeira districts and postal code prefixes) and can be
overridden manually.

The computed withholding table variant (I–XI) is shown read-only on the
same section for information. A non-resident worker's written
single-payer declaration (CIRS art. 71) is recorded with the
**Single-Payer Declaration on File** flag, shown only for non-resident
non-pensioners.

Set **Payment Date** when pay is made available on a date other than
the period end. If left blank, the period end is used. This date
selects the withholding table and month. For a
non-resident worker with the declaration on file, the **Dedução de
Entidade Única Neste Pagamento** row (`PT_IRS_SINGLE_PAYER`) on the
payslip's *Other Inputs* tab takes the verified remaining share of the
monthly minimum-wage allowance for that payment. Enter the amount
before computing (draft only); a missing or zero amount means no
allowance, and amounts are not capped or allocated across slips
automatically. The allowance is not paid or booked as its own line.
Review the amounts when duplicating a payslip — Odoo copies all inputs.

Confirm separate payments in payment-date order, one IRS payslip per
employee and month per batch. If there is more than one payment in the
month, fill in **Payment Date** for each payslip. A single monthly
payslip may still use the period end. Same-day payments can be
confirmed separately. Keep *Compute on Confirm* enabled for cumulative
IRS, and do not confirm payments for the same employee concurrently.
Payslips without a recorded historic taxable base, reversing a month,
or producing a lower liability than already withheld are blocked for
manual review. Existing finalized payslips are not migrated or
rewritten.

Salary payment method
---------------------

The **Payment Method** on each employee version (Employees → employee →
*Payroll* tab → *Portugal: Salary Payment*) points to an outbound
`account.payment.method` from Accounting. Accounting supplies the
catalog: cheque and SEPA credit transfer methods come from their
respective Accounting addons, and manual cash payment uses the standard
outbound manual method paid through a cash journal. This addon does
not select journals or create payment orders — it only records the
intended method.

The legacy **Previous Payment Method** selection stays visible
read-only until an HR manager explicitly picks an Accounting method;
existing choices are never mapped automatically.

**Salary Bank Account** selects one of the employee's standard bank
accounts for this version's salary payment arrangement. The list is
sourced from *Personal → Bank Accounts* on the employee's work contact —
this addon does not create payment orders, files, or exports, and never
marks an account as trusted for payment. The selector's **Create and Edit**
option opens a dedicated bank account form where the owner is
fixed to the employee's work contact: a new account is saved on the
contact, linked to the employee's Bank Accounts, and stays untrusted
for payment, but it is only selected on the version when the employee
form itself is saved — cancelling the form leaves the account on the
contact without changing the selection. The **Add Bank Account**
button opens the same bank account form; for an HR manager with
Partner Creation rights the created account is selected on the
contract version immediately. (The earlier Add Bank Account wizard
remains installed for compatibility.) Accounts archived later stay
stored on historical versions.

IRS withholding tables
----------------------

Retention tables are data, not code: one set per (validity period,
region, table variant I–XI), stored under *Payroll → Configuration →
IRS Withholding Tables*.

**Bundled tables load only at install time.** The module's post-init
hook imports every `data/irs/*.csv` file once, when the module is first
installed. Upgrading the module to a version that ships new CSV files
does **not** reload them — the tables on existing databases stay
untouched. To pick up new bundled tables on an existing database, open
the *Import IRS Withholding Tables* wizard and click *Load bundled
tables* (this re-imports every bundled file and is safe to run
repeatedly — each table block is replaced, never duplicated).

To install tables that are not bundled (a newer or corrected Despacho),
upload the CSV file in the same wizard. The CSV must use the bundled
format; the official AT Excel workbooks can be converted with
`scripts/xlsx_to_csv.py`.

Bundled CSV files are append-only: when a new year's tables ship, add
the new files but never remove previous years. Already-installed
databases keep their imported tables regardless (the loader only adds
or replaces blocks, it never deletes), but fresh installs only get what
is bundled — removing an old file would make backdated payslips
uncomputable on new databases.

Payroll declaration configuration
---------------------------------

On a salary rule's Portugal tab, set the DMR-AT role and income code
or contribution recipient NIPC as appropriate. Keep the IRS taxable
share for payroll withholding only. Separately set the SS remuneration
nature and choose Include or Exclude for the contribution base.
Leaving the base setting empty preserves the BASIC-category behavior.
Sequence contributing earnings before the SS deduction. The bundled
meal allowance has no declaration classification; configure separate
rules for amounts with different treatment. These settings do not
generate or submit declarations.
