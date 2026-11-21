Generate Portuguese SEPA salary payment files.

The module will turn finalized payroll runs into SEPA credit transfer
payment orders built on the posted, reconcilable net salary
liabilities of each employee, using the OCA SEPA credit transfer
infrastructure (`account_banking_sepa_credit_transfer`).

This is a draft scaffold: it declares the intended dependencies but
ships no behavior yet. The module is intentionally not installable
until the feature is implemented and its prerequisites are available.
