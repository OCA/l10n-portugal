# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class Company(models.Model):
    _inherit = "res.company"

    invoicexpress_delivery_template_id = fields.Many2one(
        "mail.template",
        "InvoiceXpress Delivery Email",
        domain="[('model', '=', 'stock.picking')]",
        default=lambda self: self.env.ref(
            "l10n_pt_stock_invoicexpress.email_template_delivey", False
        ),
        help="Used to generate the To, Cc, Subject and Body"
        " for the InvoiceXpress email sending the Delivery document.",
    )
