# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, exceptions, fields, models
from odoo.tools.misc import format_datetime


class StockPicking(models.Model):
    _inherit = "stock.picking"

    license_plate = fields.Char()
    l10npt_transport_doc_due_date = fields.Date(
        "Transport Doc. Validity",
        compute="_compute_l10npt_transport_doc_due_date",
        store=True,
        readonly=False,
    )
    invoicexpress_send_email = fields.Boolean(
        "InvX Send Email",
        compute="_compute_invoicexpress_send_email",
        store=True,
        readonly=False,
        copy=False,
        help="If unchecked, both the InvoiceXpress email"
        " and the Delivery email won't be sent.",
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

    @api.depends("l10n_pt_doc_email_enabled", "l10n_pt_doc_type")
    def _compute_invoicexpress_send_email(self):
        for delivery in self:
            delivery.invoicexpress_send_email = (
                delivery.l10n_pt_doc_email_enabled
                and delivery.l10n_pt_doc_type != "devolution"
            )

    @api.depends("scheduled_date")
    def _compute_l10npt_transport_doc_due_date(self):
        for doc in self:
            doc.l10npt_transport_doc_due_date = fields.Date.add(
                doc.scheduled_date, days=7
            )

    @api.depends(
        "move_ids.l10npt_invoicexpress_tax_id",
        "move_ids.l10npt_invoicexpress_tax_id.amount",
    )
    def _compute_l10npt_has_tax_exempt_lines(self):
        for picking in self:
            picking.l10npt_has_tax_exempt_lines = bool(
                picking.move_ids.filtered(
                    lambda m: (
                        m.l10npt_invoicexpress_tax_id
                        and not m.l10npt_invoicexpress_tax_id.amount
                    )
                )
            )

    @api.depends(
        "l10npt_has_tax_exempt_lines",
        "state",
        "sale_id.l10npt_vat_exempt_reason",
    )
    def _compute_l10npt_vat_exempt_reason(self):
        for picking in self:
            if (
                picking.l10npt_has_tax_exempt_lines
                and not picking.l10npt_vat_exempt_reason
            ):
                picking.l10npt_vat_exempt_reason = (
                    picking.sale_id.l10npt_vat_exempt_reason
                )

    @api.depends(
        "l10n_pt_doc_provider",
        "partner_id",
        "picking_type_id.invoicexpress_doc_type",
    )
    def _compute_l10n_pt_doc_type(self):
        return super()._compute_l10n_pt_doc_type()

    def _send_confirmation_email(self):
        # Only send Delivery emails if the InvoiceXpress checkbox is selected
        to_send = self.filtered("invoicexpress_send_email")
        return super(StockPicking, to_send)._send_confirmation_email()

    def _prepare_invoicexpress_lines(self):
        lines = self.move_ids.filtered("quantity")
        # Ensure Taxes are created on InvoiceXpress
        lines.l10npt_invoicexpress_tax_id.action_invoicexpress_tax_create()
        return [line._prepare_invoicexpress_line_vals() for line in lines]

    def _prepare_invoicexpress_vals(self):
        self.ensure_one()
        shipping_date = fields.Datetime.add(fields.Datetime.now(), minutes=5)
        customer = self.partner_id.commercial_partner_id
        customer_vals = customer.set_invoicexpress_contact(company=self.company_id)
        if self.location_id.usage == "internal":  # Outgoing
            address_from = self.picking_type_id.warehouse_id.partner_id
            address_to = self.partner_id
        elif self.location_dest_id.usage == "internal":  # Incoming => Return
            address_from = self.partner_id
            address_to = self.picking_type_id.warehouse_id.partner_id
        else:
            address_from = self.picking_type_id.warehouse_id.partner_id
            address_to = self.partner_id
        addr_from_vals = address_from._prepare_invoicexpress_shipping_vals()
        addr_to_vals = address_to._prepare_invoicexpress_shipping_vals()

        doctype = self.l10n_pt_doc_type
        item_vals = self._prepare_invoicexpress_lines()
        vals = {
            doctype: {
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
        if self.l10npt_vat_exempt_reason:
            vals[doctype]["tax_exemption"] = self.l10npt_vat_exempt_reason.code
        return vals

    def _prepare_invoicexpress_email_vals(self, ignore_no_config=False):
        self.ensure_one()
        template_id = self.company_id.invoicexpress_delivery_template_id
        if not template_id and not ignore_no_config:
            raise exceptions.UserError(
                self.env._(
                    "Please configure the InvoiceXpress Delivery email template"
                    " at Settings > General Setting, InvoiceXpress section"
                )
            )
        values = template_id._generate_template(
            [self.id], ["subject", "body_html", "email_to", "email_cc"]
        )[self.id]
        if not values.get("email_to") and not ignore_no_config:
            raise exceptions.UserError(
                self.env._("No address to send delivery document email to.")
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
