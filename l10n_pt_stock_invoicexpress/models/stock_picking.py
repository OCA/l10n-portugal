# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from markupsafe import Markup

from odoo import _, api, exceptions, fields, models
from odoo.tools import format_datetime

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.depends("invoicexpress_doc_type", "company_id.has_invoicexpress")
    def _compute_can_invoicexpress(self):
        for delivery in self:
            delivery.can_invoicexpress = (
                delivery.company_id.has_invoicexpress
                and delivery.invoicexpress_doc_type
            )

    @api.depends("can_invoicexpress", "company_id.invoicexpress_delivery_template_id")
    def _compute_can_invoicexpress_email(self):
        for delivery in self:
            delivery.can_invoicexpress_email = (
                delivery.can_invoicexpress
                and delivery.company_id.invoicexpress_delivery_template_id
            )

    @api.depends("can_invoicexpress_email", "invoicexpress_doc_type")
    def _compute_invoicexpress_send_email(self):
        for delivery in self:
            delivery.invoicexpress_send_email = (
                delivery.can_invoicexpress_email
                and delivery.invoicexpress_doc_type != "devolution"
            )

    @api.depends("scheduled_date")
    def _compute_l10npt_transport_doc_due_date(self):
        for doc in self:
            doc.l10npt_transport_doc_due_date = fields.Date.add(
                doc.scheduled_date, days=7
            )

    @api.depends("picking_type_id")
    def _compute_invoicexpress_doc_type(self):
        """
        Return the doc type, read from the Operation Type.
        Also detect devolutions, and then use the appropriate type instead.
        """
        for pick in self:
            pick_doc_type = pick.picking_type_id.invoicexpress_doc_type
            country = pick.partner_id.country_id
            is_PT = not country or country.code == "PT"
            # TODO: Automatic support for devolutions
            # Disabled for now, should be used for supplier devolutions only?
            # return_orig_moves = pick.move_ids_without_package.origin_returned_move_id
            # if return_orig_moves.mapped("picking_id.invoicexpress_id"):
            #     pick.invoicexpress_doc_type = "devolution"
            if pick_doc_type and pick_doc_type != "none" and is_PT:
                pick.invoicexpress_doc_type = pick_doc_type

    @api.depends(
        "move_line_ids.quantity_product_uom",
        "move_line_ids.move_id.l10npt_invoicexpress_tax_id",
        "move_line_ids.product_id.taxes_id",
    )
    def _compute_l10npt_has_tax_exempt_lines(self):
        for picking in self:
            picking.l10npt_has_tax_exempt_lines = any(
                (tax := line._get_invoicexpress_tax()) and not tax.amount
                for line in picking.move_line_ids
                if line.quantity_product_uom
            )

    @api.depends(
        "l10npt_has_tax_exempt_lines",
        "state",
        "sale_id.l10npt_vat_exempt_reason",
    )
    def _compute_l10npt_vat_exempt_reason(self):
        # Skip done/cancel pickings to avoid recomputing large historical
        # datasets on module install and to protect finalised records.
        for picking in self.filtered(lambda p: p.state not in ("cancel", "done")):
            if (
                picking.l10npt_has_tax_exempt_lines
                and not picking.l10npt_vat_exempt_reason
            ):
                picking.l10npt_vat_exempt_reason = (
                    picking.sale_id.l10npt_vat_exempt_reason
                )

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
    invoicexpress_send_email = fields.Boolean(
        "InvX Send Email",
        compute="_compute_invoicexpress_send_email",
        store=True,
        readonly=False,
        copy=False,
        help="If unchecked, both the InvoiceXpress email"
        " and the Delivery email won't be sent.",
    )
    invoicexpress_doc_type = fields.Selection(
        [
            ("transport", "Guia de Transporte / Transport"),
            ("shipping", "Guia de Remessa / Shipping"),
            ("devolution", "Devolução / Return"),
        ],
        string="InvX Doc Type",
        compute="_compute_invoicexpress_doc_type",
        store=True,
        readonly=False,
        copy=False,
        help="Select the type of legal delivery document"
        " to be created by InvoiceXpress.",
    )
    invoicexpress_transport_date = fields.Datetime(
        string="InvX Transport Document Date",
        help="Date for the InvoiceXpress transport document. "
        "If not set, the shipping date will be used.",
        copy=False,
    )
    l10npt_has_tax_exempt_lines = fields.Boolean(
        compute="_compute_l10npt_has_tax_exempt_lines"
    )
    l10npt_vat_exempt_reason = fields.Many2one(
        "account.l10n_pt.vat.exempt.reason",
        string="VAT Exempt Reason",
        compute="_compute_l10npt_vat_exempt_reason",
        store=True,
        readonly=False,
        help="VAT exemption reason to send to InvoiceXpress when the "
        "transport document contains exempt items.",
    )

    def _send_confirmation_email(self):
        # Only send Delivery emails if the InvoiceXpress checkbox is selected
        to_send = self.filtered("invoicexpress_send_email")
        return super(StockPicking, to_send)._send_confirmation_email()

    @api.model
    def _get_invoicexpress_prefix(self, doctype):
        return {
            "transport": "GT",
            "shipping": "GR",
            "devolution": "GD",
        }.get(doctype)

    def _prepare_invoicexpress_lines(self):
        # Build one API line per detailed operation, including products inside
        # packages (package move lines may not have a related stock.move).
        # Missing product or zero quantity move lines are kept and use filler
        # values for the fields that are required by the InvoiceXpress API.
        move_lines = self.move_line_ids
        # Ensure Taxes are created on InvoiceXpress
        taxes = self.env["account.tax"].union(
            *[line._get_invoicexpress_tax() for line in move_lines]
        )
        taxes.action_invoicexpress_tax_create()
        return [line._prepare_invoicexpress_line_vals() for line in move_lines]

    def _prepare_invoicexpress_vals(self):
        self.ensure_one()
        shipping_date = self.invoicexpress_transport_date or fields.Datetime.add(
            fields.Datetime.now(), minutes=5
        )
        if shipping_date < fields.Datetime.now():
            raise exceptions.ValidationError(
                _("Scheduled Date should be later than the current datetime!")
            )
        customer = self.partner_id.commercial_partner_id
        customer_vals = customer.set_invoicexpress_contact(company=self.company_id)
        if self.location_id.usage == "internal":  # Outgoing
            address_from = self.picking_type_id.warehouse_id.partner_id
            address_to = self.partner_id
        elif self.location_dest_id.usage == "internal":  # Incoming => Return
            address_from = self.partner_id
            address_to = self.picking_type_id.warehouse_id.partner_id
        addr_from_vals = address_from._prepare_invoicexpress_shipping_vals()
        addr_to_vals = address_to._prepare_invoicexpress_shipping_vals()

        doctype = self.invoicexpress_doc_type
        item_vals = self._prepare_invoicexpress_lines()
        vals = {
            doctype: {
                # Document date is always today
                # "date": shipping_date.strftime("%d/%m/%Y"),
                "date": fields.Date.today().strftime("%d/%m/%Y"),
                "due_date": self.l10npt_transport_doc_due_date.strftime("%d/%m/%Y"),
                # Expected loading datetime can be in the future
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
        if self.l10npt_vat_exempt_reason:
            vals[doctype]["tax_exemption"] = self.l10npt_vat_exempt_reason.code
        return vals

    def _update_invoicexpress_status(self):
        inv_xpress_link_name = _("View Document")
        inv_xpress_link = (
            f"<a class='btn btn-info mr-2' target='new' "
            f"href='{self.invoicexpress_permalink}'>{inv_xpress_link_name}</a>"
        )
        msg = _(
            "InvoiceXpress record has been created for this delivery order:<ul>"
            "<li>Number: {inv_xpress_num}</li>"
            "<li>{inv_xpress_link}</li></ul>"
        ).format(
            inv_xpress_num=self.invoicexpress_number, inv_xpress_link=inv_xpress_link
        )
        self.message_post(body=Markup(msg))

    def action_create_invoicexpress_delivery(self):
        """
        Generate legal "Guia de Transporte", for customer deliveries
        or transfers between warehouses.
        We allow generating more than one for the same Odoo document.
        """
        InvoiceXpress = self.env["account.invoicexpress"]
        for delivery in self.filtered("can_invoicexpress"):
            # If picking is done and already has an InvoiceXpress document,
            # clear the previous data before creating a new one
            if delivery.state == "done" and delivery.invoicexpress_id:
                delivery.write(
                    {
                        "invoicexpress_id": False,
                        "invoicexpress_number": False,
                        "invoicexpress_permalink": False,
                    }
                )

            if (
                delivery.l10npt_has_tax_exempt_lines
                and not delivery.l10npt_vat_exempt_reason
            ):
                raise exceptions.UserError(
                    _("A tax exemption reason must be provided.")
                )

            payload = delivery._prepare_invoicexpress_vals()
            doctype = delivery.invoicexpress_doc_type
            response = InvoiceXpress.call(
                delivery.company_id, f"{doctype}s.json", "POST", payload=payload
            )
            values = response.json().get(doctype)
            if not values:
                raise exceptions.UserError(
                    _("Something went wrong: the InvoiceXpress response looks empty.")
                )
            delivery.invoicexpress_id = values.get("id")
            delivery.invoicexpress_permalink = values.get("permalink")
            response1 = InvoiceXpress.call(
                delivery.company_id,
                "{}s/{}/change-state.json".format(doctype, values["id"]),
                "PUT",
                payload={doctype: {"state": "finalized"}},
            )
            values1 = response1.json().get(doctype)
            prefix = self._get_invoicexpress_prefix(doctype)
            seqnum = values1["inverted_sequence_number"]
            invx_number = f"{prefix} {seqnum}"
            delivery.invoicexpress_number = invx_number
            delivery._update_invoicexpress_status()

    def _prepare_invoicexpress_email_vals(self, ignore_no_config=False):
        self.ensure_one()
        template_id = self.company_id.invoicexpress_delivery_template_id
        values = template_id._generate_template(
            [self.id], ["subject", "body_html", "email_to", "email_cc"]
        )[self.id]
        if not template_id and not ignore_no_config:
            raise exceptions.UserError(
                _(
                    "Please configure the InvoiceXpress Delivery email template"
                    " at Settings > General Setting, InvoiceXpress section"
                )
            )
        if not values.get("email_to") and not ignore_no_config:
            raise exceptions.UserError(
                _("No address to send delivery document email to.")
            )
        email_data = None
        if template_id and values["email_to"]:
            email_data = {
                "message": {
                    "client": {"email": values["email_to"], "save": "0"},
                    "cc": values["email_cc"],
                    "subject": values["subject"],
                    "body": values["body_html"],
                }
            }
        return email_data

    def action_send_invoicexpress_delivery(self, ignore_no_config=False):
        InvoiceXpress = self.env["account.invoicexpress"]
        for delivery in self.filtered("invoicexpress_send_email"):
            if not delivery.invoicexpress_id:
                raise exceptions.UserError(
                    _("Delivery %s is not registered in InvoiceXpress yet."),
                    delivery.name,
                )
            doctype = delivery.invoicexpress_doc_type
            endpoint = f"{doctype}s/{delivery.invoicexpress_id}/email-document.json"
            payload = delivery._prepare_invoicexpress_email_vals(ignore_no_config)
            if payload:
                InvoiceXpress.call(
                    delivery.company_id, endpoint, "PUT", payload=payload
                )
                msg = _(
                    "Email sent by InvoiceXpress:<ul><li>To: "
                    "{email}/li><li>Cc: {cc}</li></ul>"
                ).format(
                    email=payload["message"]["client"]["email"],
                    cc=payload["message"]["cc"] or _("None"),
                )
                delivery.message_post(body=Markup(msg))

    def button_validate(self):
        """
        Automatically generate legal transport docs for PT customers
        """
        res = super().button_validate()
        if res is True:  # do not enter if the result is a dict, only if it is True
            missing_country = self.filtered(
                lambda x: x.can_invoicexpress and not x.partner_id.country_id
            )
            if missing_country:
                raise exceptions.UserError(_("Please set the country of the partner."))
            to_invoicexpress = self.filtered(
                lambda x: x.partner_id.country_id.code == "PT"
                and x.picking_type_id.invoicexpress_auto_create
            )
            to_invoicexpress.action_create_invoicexpress_delivery()
            to_invoicexpress.action_send_invoicexpress_delivery(ignore_no_config=True)
        return res
