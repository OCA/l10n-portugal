# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    moloni_doc_type = fields.Selection(
        [
            ("invoices", "Invoice"),
            ("invoiceReceipts", "Invoice-Receipt"),
            ("simplifiedInvoices", "Simplified Invoice"),
            ("debitNotes", "Debit Note"),
            ("none", "No Moloni document"),
        ],
        help="Select the type of legal document to be created by Moloni.",
    )
