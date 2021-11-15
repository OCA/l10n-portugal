# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    def _default_invoicexpress_doc_type(self):
        return (
            "transport"
            if self.company_id.has_invoicexpress and self.code == "outgoing"
            else "none"
        )

    invoicexpress_doc_type = fields.Selection(
        [
            ("transport", "Guia de Transporte / Transport"),
            ("shipping", "Guia de Remessa / Shipping"),
            ("none", "No InvoiceXpress document"),
        ],
        default="transport",
        help="Select the type of legal delivery document"
        " to be created by InvoiceXpress. If unset",
    )
