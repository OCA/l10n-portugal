Planned usage. This describes the intended flow for review; the
module does not export files yet.

1. Finalize a payroll run, then review the eligible posted salary
   payables and prepare a draft outgoing payment order with the
   dedicated salary mode, the company EUR debit account and the
   requested execution date.
2. Check the beneficiary count, total amount, debit account and
   execution date before generating the XML through the payment
   order.
3. Download the file and upload it manually to the bank portal, then
   authorize the payment there. Downloading does not mark anything as
   uploaded or paid.
4. Track bank rejection or acceptance separately from the payment
   order. A replacement file is created only after a rejection or a
   confirmed non-submission; never silently resend a file that might
   have been accepted.
5. Re-downloading returns the same frozen file and references. Lines
   with missing or invalid IBANs, inconsistent balances or duplicates
   are blocked for review instead of being exported.
