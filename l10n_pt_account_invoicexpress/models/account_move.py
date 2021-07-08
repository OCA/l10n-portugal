# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, exceptions, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    journal_type = fields.Selection(
        related="journal_id.type", string="Journal Type", readonly=True
    )
    invoicexpress_id = fields.Char("InvoiceXpress ID", copy=False, readonly=True)
    invoicexpress_permalink = fields.Char(
        "InvoiceXpress Doc Link", copy=False, readonly=True
    )
    can_invoicexpress = fields.Boolean(compute="_compute_can_invoicexpress")
    can_invoicexpress_email = fields.Boolean(compute="_compute_can_invoicexpress_email")

    @api.depends("move_type", "journal_id", "company_id.invoicexpress_api_key")
    def _compute_can_invoicexpress(self):
        for invoice in self:
            invoice.can_invoicexpress = (
                invoice.is_sale_document() and invoice.company_id.invoicexpress_api_key
            )

    @api.depends("can_invoicexpress", "company_id.invoicexpress_template_id")
    def _compute_can_invoicexpress_email(self):
        for invoice in self:
            invoice.can_invoicexpress_email = (
                invoice.can_invoicexpress
                and invoice.company_id.invoicexpress_template_id
            )

    def _get_invoicexpress_doctype(self):
        """
        The type of document you wish to send by email: invoices, invoice_receipts,
        simplified_invoices, vat_moss_invoices, credit_notes or debit_notes.
        """
        doctype = "invoices"
        if self.move_type == "out_refund":
            doctype = "credit_notes"
        return doctype

    def _prepare_invoicexpress_lines(self):
        # FIXME: set user lang, based on country?
        lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ("line_section", "line_note")
        )
        # Ensure Taxes are created on InvoiceXpress
        lines.mapped("tax_ids").action_invoicexpress_tax_create()
        items = []
        for line in lines:
            tax = line.tax_ids[:1]
            # If not tax set, force zero VAT
            tax_detail = {"name": tax.name or "IVA0", "value": tax.amount or 0.0}
            items.append(
                {
                    "name": line.product_id.default_code
                    or line.product_id.display_name,
                    "description": line.name,
                    "unit_price": line.price_unit,
                    "quantity": line.quantity,
                    "discount": line.discount,
                    "tax": tax_detail,
                }
            )
        return items

    def _prepare_invoicexpress_vals(self):
        self.ensure_one()
        if not self.invoice_date and self.invoice_date_due:
            raise exceptions.UserError(
                _("Kindly add the invoice date and invoice due date.")
            )

        customer = self.partner_id._prepare_invoicexpress_vals()
        items = self._prepare_invoicexpress_lines()
        invoice_data = {
            "invoice": {
                "date": self.invoice_date.strftime("%d/%m/%Y"),
                "due_date": self.invoice_date_due.strftime("%d/%m/%Y"),
                "reference": self.ref or "",
                "client": customer,
                "items": items,
            },
            "proprietary_uid": "%s.%s" % (self.name, self.env.cr.dbname),
        }
        exempt_code = self.l10npt_vat_exempt_reason.code
        if exempt_code:
            invoice_data["invoice"]["tax_exemption"] = exempt_code
        if self.company_id.currency_id != self.currency_id:
            currency_rate = self.env["res.currency"]._get_conversion_rate(
                self.company_id.currency_id,
                self.currency_id,
                self.company_id,
                self.invoice_date,
            )
            invoice_data.update(
                {"currency_code": self.currency_id.name, "rate": str(currency_rate)}
            )
        return invoice_data

    def _update_invoicexpress_status(self):
        inv_xpress_link = _(
            " <a class='btn btn-info mr-2' href={}>View Document</a>"
        ).format(self.invoicexpress_permalink)
        msg = _(
            "InvoiceXpress record has been created for this invoice:"
            "<ul><li>InvoiceXpress Id: {inv_xpress_id}</li>"
            "<li>{inv_xpress_link}</li></ul>"
        ).format(inv_xpress_id=self.invoicexpress_id, inv_xpress_link=inv_xpress_link)
        self.message_post(body=msg)

    def action_create_invoicexpress_invoice(self):
        InvoiceXpress = self.env["account.invoicexpress"]
        for invoice in self.filtered("can_invoicexpress"):
            doctype = invoice._get_invoicexpress_doctype()
            payload = invoice._prepare_invoicexpress_vals()
            response = InvoiceXpress.call(
                invoice.company_id, "{}.json".format(doctype), "POST", payload=payload
            ).json()
            values = response.get("invoice") or response.get("credit_note")
            if values:
                invoice.invoicexpress_id = values.get("id")
                invoice.invoicexpress_permalink = values.get("permalink")
                response1 = InvoiceXpress.call(
                    invoice.company_id,
                    "{}/{}/change-state.json".format(doctype, invoice.invoicexpress_id),
                    "PUT",
                    payload={"invoice": {"state": "finalized"}},
                    raise_errors=False,
                ).json()
                values1 = response1.get("invoice") or response1.get("credit_note")
                invx_number = values1 and values1["inverted_sequence_number"]
                if invx_number:
                    if invoice.payment_reference == invoice.name:
                        invoice.payment_reference = invx_number
                    invoice.name = invx_number
                invoice._update_invoicexpress_status()

    def _prepare_invoicexpress_email_vals(self):
        self.ensure_one()
        template_id = self.company_id.invoicexpress_template_id
        values = template_id.generate_email(
            self.id, ["subject", "body_html", "email_to", "email_cc"]
        )
        if not template_id:
            raise exceptions.UserError(
                _(
                    "Please configure the InvoiceXpress email template"
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

    def action_send_invoicexpress_email(self):
        InvoiceXpress = self.env["account.invoicexpress"]
        for invoice in self.filtered("can_invoicexpress_email"):
            if not invoice.invoicexpress_id:
                raise exceptions.UserError(
                    _("Invoice %s is not registerd in InvoiceXpress yet."), invoice.name
                )
            endpoint = "invoices/{}/email-document.json".format(
                invoice.invoicexpress_id
            )
            payload = invoice._prepare_invoicexpress_email_vals()
            if not payload["message"]["client"]["email"]:
                invoice.message_post(
                    body=_("No email to send the InvoiceXpress document to.")
                )
            else:
                InvoiceXpress.call(invoice.company_id, endpoint, "PUT", payload=payload)
                msg = _(
                    "Email sent by InvoiceXpress:<ul><li>To: {}</li><li>Cc: {}</li></ul>"
                ).format(
                    payload["message"]["client"]["email"],
                    payload["message"]["cc"] or _("None"),
                )
                invoice.message_post(body=msg)

    @api.depends("restrict_mode_hash_table", "state")
    def _compute_show_reset_to_draft_button(self):
        super()._compute_show_reset_to_draft_button()
        self.filtered("invoicexpress_id").write({"show_reset_to_draft_button": False})

    def action_post(self):
        res = super().action_post()
        for invoice in self:
            if not invoice.invoicexpress_id:
                invoice.action_create_invoicexpress_invoice()
                invoice.action_send_invoicexpress_email()
        return res
