# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class Company(models.Model):
    _inherit = "res.company"

    invoicexpress_account_name = fields.Char(string="InvoiceXpress Account Name")
    invoicexpress_api_key = fields.Char(string="InvoiceXpress API Key")
    invoicexpress_template_id = fields.Many2one(
        "mail.template",
        "InvoiceXpress Email Template",
        domain="[('model', '=', 'account.move')]",
        default=lambda self: self.env.ref(
            "l10n_pt_account_invoicexpress.email_template_invoice", False
        ),
        help="Used to generate the To, Cc, Subject and Body"
        " for the email sent by the InvoiceXpress service",
    )
