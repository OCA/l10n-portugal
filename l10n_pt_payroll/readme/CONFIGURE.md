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
same section for information.

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
