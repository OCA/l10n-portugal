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
    invoicexpress_account_name = fields.Char(string="InvoiceXpress Account Name")
    invoicexpress_api_key = fields.Char(
        string="InvoiceXpress API Key",
        groups="account.group_account_manager",
        copy=False,
    )
    invoicexpress_template_id = fields.Many2one(
        "mail.template",
        string="InvoiceXpress Email Template",
        domain="[('model', '=', 'account.move')]",
        help="Set a template to enable Email via Provider. "
        "Leave empty to send invoices from Odoo only.",
    )
    invoicexpress_provider_code = fields.Char(related="l10n_pt_doc_provider_id.code")
