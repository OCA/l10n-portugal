# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, exceptions, fields, models
from odoo.tools import format_datetime
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    license_plate = fields.Char()
    invoicexpress_id = fields.Char("InvoiceXpress ID", copy=False, readonly=True)
    invoicexpress_permalink = fields.Char(
        "InvoiceXpress Doc Link", copy=False, readonly=True
    )
    l10npt_transport_doc_due_date = fields.Date(
        "Transport Doc. Validity",
        compute="_compute_l10npt_transport_doc_due_date",
        store=True,
        readonly=False,
    )

    @api.depends("scheduled_date")
    def _compute_l10npt_transport_doc_due_date(self):
        for doc in self:
            doc.l10npt_transport_doc_due_date = fields.Date.add(
                doc.scheduled_date, days=7
            )

    def _get_invoicexpress_doctype(self):
        return "shippings" if self.picking_type_id.code != "incoming" else "devolutions"

    def _prepare_invoicexpress_lines(self):
        lines = self.move_lines.filtered(
            lambda l: l.quantity_done and l.picking_code == "outgoing"
        )
        # Ensure Taxes are created on InvoiceXpress
        lines.mapped("sale_line_id.tax_id").action_invoicexpress_tax_create()
        items = []
        for line in lines:
            tax = line.sale_line_id.tax_id[:1]
            tax_detail = {"name": tax.name, "value": tax.amount} if tax else {}
            items.append(
                {
                    "name": line.product_id.default_code
                    or line.product_id.display_name,
                    "description": line.name or "",
                    "unit_price": line.sale_line_id.price_unit,
                    "quantity": line.quantity_done,
                    "discount": line.sale_line_id.discount,
                    "tax": tax_detail,
                }
            )
        return items

    def _prepare_invoicexpress_vals(self):
        self.ensure_one()
        if self.scheduled_date and self.scheduled_date < fields.Datetime.now():
            raise exceptions.ValidationError(
                _("Scheduled Date should be bigger then current datetime!")
            )
        warehouse = self.location_id.get_warehouse()
        customer = self.partner_id.commercial_partner_id
        customer_vals = customer._prepare_invoicexpress_vals()
        addr_from_vals = warehouse.partner_id._prepare_invoicexpress_shipping_vals()
        addr_to_vals = self.partner_id._prepare_invoicexpress_shipping_vals()
        item_vals = self._prepare_invoicexpress_lines()
        return {
            "shipping": {
                "date": self.scheduled_date.strftime("%d/%m/%Y"),
                "due_date": (
                    self.l10npt_transport_doc_due_date or self.scheduled_date
                ).strftime("%d/%m/%Y"),
                "loaded_at": format_datetime(
                    self.env, self.scheduled_date, dt_format="dd/MM/yyyy hh:mm:ss"
                ),
                "license_plate": self.license_plate or "",
                "address_from": addr_from_vals,
                "address_to": addr_to_vals,
                "reference": self.origin or "",
                "client": customer_vals,
                "items": item_vals,
            }
        }

    def _update_invoicexpress_status(self, result):
        vals = {
            "invoicexpress_id": result.get("id"),
            "invoicexpress_permalink": result.get("permalink"),
        }
        self.update(vals)

        # post the message on chatter
        inv_xpress_link = _(
            "<a class='btn btn-info mr-2' href={}>View Document</a>"
        ).format(result.get("permalink"))
        msg = _(
            "InvoiceXpress record has been created for this delivery order:"
            "<ul><li>InvoiceXpress Id: {inv_xpress_id}</li>"
            "<li>{inv_xpress_link}</li></ul>"
        ).format(inv_xpress_id=result.get("id"), inv_xpress_link=inv_xpress_link)
        self.message_post(body=msg)

    def action_create_invoicexpress_delivery(self):
        """
        Generate legal "Guia de Transporte", for customer deliveries
        or transfers between warehouses.
        We allow generating more than one for the same Odoo document.
        """
        InvoiceXpress = self.env["account.invoicexpress"]
        for delivery in self.filtered(lambda x: x.picking_type_code != "incoming"):
            doctype = delivery._get_invoicexpress_doctype()
            payload = delivery._prepare_invoicexpress_vals()
            response = InvoiceXpress.call(
                "{}.json".format(doctype), "POST", payload=payload
            )
            values = response.json().get("shipping")
            if values:
                delivery._update_invoicexpress_status(values)
                InvoiceXpress.call(
                    "{}/{}/change-state.json".format(doctype, values["id"]),
                    "PUT",
                    payload={"shipping": {"state": "finalized"}},
                )

    def _prepare_invoicexpress_email_vals(self):
        self.ensure_one()
        ICPSudo = self.env["ir.config_parameter"].sudo()
        eval_email_to = ICPSudo.get_param(
            "invoicexpress.stock_email_to", "self.env.user.email"
        )
        eval_email_cc = ICPSudo.get_param("invoicexpress.stock_email_cc")
        eval_context = {"self": self}
        email_to = safe_eval(eval_email_to, eval_context)
        email_cc = eval_email_cc and safe_eval(eval_email_cc, eval_context)
        if not email_to:
            raise exceptions.UserError(_("Kindly Configure the email address."))
        email_data = {
            "message": {
                "client": {"email": email_to, "save": "0"},
                "cc": email_cc,
                "subject": _("Delivery from InvoiceXpress"),
                "body": _("InvoiceXpress Document"),
            }
        }
        return email_data

    def action_send_invoicexpress_delivery(self):
        InvoiceXpress = self.env["account.invoicexpress"]
        for delivery in self:
            if not delivery.invoicexpress_id:
                raise exceptions.UserError(
                    _("Delivery %s is not registerd in InvoiceXpress yet."),
                    delivery.name,
                )
            doctype = delivery._get_invoicexpress_doctype()
            endpoint = "{}/{}/email-document.json".format(
                doctype, delivery.invoicexpress_id
            )
            payload = delivery._prepare_invoicexpress_email_vals()
            InvoiceXpress.call(endpoint, "PUT", payload=payload)
            msg = _(
                "Email sent by InvoiceXpress:<ul><li>To: {}</li><li>Cc: {}</li></ul>"
            ).format(
                payload["message"]["client"]["email"],
                payload["message"]["cc"] or _("None"),
            )
            delivery.message_post(body=msg)
