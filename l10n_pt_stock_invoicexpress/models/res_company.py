# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


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

    def _update_default_doctype(self):
        """
        When enabling InvoiceXpress, apply defaults
        to existing delivery/outgoing operation Types
        that don't have a doc type set yet.
        """
        for company in self.filtered("has_invoicexpress"):
            pick_types_todo = self.env["stock.picking.type"].search(
                [
                    ("company_id", "=", company.id),
                    ("invoicexpress_doc_type", "=", False),
                ]
            )
            for picktype in pick_types_todo:
                picktype.invoicexpress_doc_type = (
                    picktype._default_invoicexpress_doc_type()
                )

    @api.model
    def create(self, vals):
        res = super().create(vals)
        if [x in vals for x in ("invoicexpress_account_name", "invoicexpress_api_key")]:
            res._update_default_doctype()
        return res

    def write(self, vals):
        res = super().write(vals)
        if [x in vals for x in ("invoicexpress_account_name", "invoicexpress_api_key")]:
            self._update_default_doctype()
        return res
