# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    invoicexpress_doc_type = fields.Selection(
        [
            ("invoice", "Invoice"),
            ("invoice_receipt", "Invoices Receipt"),
            ("simplified_invoice", "Simplified Invoice"),
            ("none", "No InvoiceXpress document"),
        ],
        help="Select the type of legal invoice document"
        " to be created by InvoiceXpress.",
    )
