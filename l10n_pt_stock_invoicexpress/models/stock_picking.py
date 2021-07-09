# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, exceptions, fields, models
from odoo.tools import format_datetime

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    license_plate = fields.Char()
    invoicexpress_id = fields.Char("InvoiceXpress ID", copy=False, readonly=True)
    invoicexpress_number = fields.Char(
        "InvoiceXpress Number", copy=False, readonly=True
    )
    invoicexpress_permalink = fields.Char(
        "InvoiceXpress Doc Link", copy=False, readonly=True
    )
    l10npt_transport_doc_due_date = fields.Date(
        "Transport Doc. Validity",
        compute="_compute_l10npt_transport_doc_due_date",
        store=True,
        readonly=False,
    )
    can_invoicexpress = fields.Boolean(compute="_compute_can_invoicexpress")
    can_invoicexpress_email = fields.Boolean(compute="_compute_can_invoicexpress_email")

    @api.depends("picking_type_id", "company_id.invoicexpress_api_key")
    def _compute_can_invoicexpress(self):
        for delivery in self:
            delivery.can_invoicexpress = (
                delivery.picking_type_id.code != "incoming"
                and delivery.company_id.invoicexpress_api_key
            )

    @api.depends("can_invoicexpress", "company_id.invoicexpress_delivery_template_id")
    def _compute_can_invoicexpress_email(self):
        for delivery in self:
            delivery.can_invoicexpress_email = (
                delivery.can_invoicexpress
                and delivery.company_id.invoicexpress_delivery_template_id
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
            # tax = line.sale_line_id.tax_id[:1]
            # tax_detail = {"name": tax.name, "value": tax.amount} if tax else {}
            items.append(
                {
                    "name": line.product_id.default_code
                    or line.product_id.display_name,
                    "description": line.name or "",
                    "unit_price": 0.0,  # line.sale_line_id.price_unit,
                    "quantity": line.quantity_done,
                    # "discount": line.sale_line_id.discount,
                    # "tax": tax_detail,
                }
            )
        return items

    def _prepare_invoicexpress_vals(self):
        self.ensure_one()
        shipping_date = fields.Datetime.add(fields.Datetime.now(), minutes=5)
        if shipping_date < fields.Datetime.now():
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
                "date": shipping_date.strftime("%d/%m/%Y"),
                "due_date": (
                    self.l10npt_transport_doc_due_date or shipping_date
                ).strftime("%d/%m/%Y"),
                "loaded_at": format_datetime(
                    self.env, shipping_date, dt_format="dd/MM/yyyy HH:mm:ss"
                ),
                "license_plate": self.license_plate or "",
                "address_from": addr_from_vals,
                "address_to": addr_to_vals,
                "reference": self.origin or "",
                "client": customer_vals,
                "items": item_vals,
            }
        }

    def _update_invoicexpress_status(self):
        inv_xpress_link = _(
            "<a class='btn btn-info mr-2' href={}>View Document</a>"
        ).format(self.invoicexpress_permalink)
        msg = _(
            "InvoiceXpress record has been created for this delivery order:<ul>"
            "<li>Number: {inv_xpress_num}</li>"
            "<li>{inv_xpress_link}</li></ul>"
        ).format(
            inv_xpress_num=self.invoicexpress_number, inv_xpress_link=inv_xpress_link
        )
        self.message_post(body=msg)

    def action_create_invoicexpress_delivery(self):
        """
        Generate legal "Guia de Transporte", for customer deliveries
        or transfers between warehouses.
        We allow generating more than one for the same Odoo document.
        """
        InvoiceXpress = self.env["account.invoicexpress"]
        for delivery in self.filtered("can_invoicexpress"):
            doctype = delivery._get_invoicexpress_doctype()
            payload = delivery._prepare_invoicexpress_vals()
            response = InvoiceXpress.call(
                delivery.company_id, "{}.json".format(doctype), "POST", payload=payload
            )
            values = response.json().get("shipping")
            if values:
                delivery.invoicexpress_id = values.get("id")
                delivery.invoicexpress_permalink = values.get("permalink")
                response1 = InvoiceXpress.call(
                    delivery.company_id,
                    "{}/{}/change-state.json".format(doctype, values["id"]),
                    "PUT",
                    payload={"shipping": {"state": "finalized"}},
                )
                values1 = response1.json().get("shipping")
                delivery.invoicexpress_number = values1["inverted_sequence_number"]
                delivery._update_invoicexpress_status()

    def _prepare_invoicexpress_email_vals(self):
        self.ensure_one()
        template_id = self.company_id.invoicexpress_delivery_template_id
        values = template_id.generate_email(
            self.id, ["subject", "body_html", "email_to", "email_cc"]
        )
        if not template_id:
            raise exceptions.UserError(
                _(
                    "Please configure the InvoiceXpress Delivery email template"
                    " at Settings > General Setting, InvoiceXpress section"
                )
            )
        email_data = {
            "message": {
                "client": {"email": values["email_to"], "save": "0"},
                "cc": values["email_cc"],
                "subject": values["subject"],
                "body": values["body_html"],
            }
        }
        return email_data

    def action_send_invoicexpress_delivery(self):
        InvoiceXpress = self.env["account.invoicexpress"]
        for delivery in self.filtered("can_invoicexpress_email"):
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

            if not payload["message"]["client"]["email"]:
                delivery.message_post(
                    body=_("No email to send the InvoiceXpress document to.")
                )
            else:
                InvoiceXpress.call(
                    delivery.company_id, endpoint, "PUT", payload=payload
                )
                msg = _(
                    "Email sent by InvoiceXpress:<ul><li>To: {}</li><li>Cc: {}</li></ul>"
                ).format(
                    payload["message"]["client"]["email"],
                    payload["message"]["cc"] or _("None"),
                )
                delivery.message_post(body=msg)

    def _action_done(self):
        """
        Automatically generate legal transport docs for PT customers
        """
        res = super()._action_done()
        to_invoicexpress = self.filtered(lambda x: x.partner_id.country_id.code == "PT")
        to_invoicexpress.action_create_invoicexpress_delivery()
        to_invoicexpress.action_send_invoicexpress_delivery()
        return res
