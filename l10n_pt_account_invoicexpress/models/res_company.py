# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class Company(models.Model):
    _inherit = "res.company"

    @api.depends("country_code", "invoicexpress_account_name", "invoicexpress_api_key")
    def _compute_has_invoicexpress(self):
        for company in self:
            company.has_invoicexpress = (
                company.country_code == "PT"
                and company.invoicexpress_account_name
                and company.invoicexpress_api_key
            )

    invoicexpress_account_name = fields.Char(string="InvoiceXpress Account Name")
    invoicexpress_api_key = fields.Char(string="InvoiceXpress API Key")
    has_invoicexpress = fields.Boolean(
        compute="_compute_has_invoicexpress",
        help="Easy to use indicator if InvoiceXpress is enabled and can be used",
    )

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
