# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, exceptions, fields, models
from odoo.tools import safe_eval


class AccountMove(models.Model):
    _inherit = "account.move"

    journal_type = fields.Selection(
        related="journal_id.type", string="Journal Type", readonly=True
    )
    invoicexpress_id = fields.Char("InvoiceXpress ID", copy=False, readonly=True)
    invoicexpress_permalink = fields.Char(
        "InvoiceXpress Doc Link", copy=False, readonly=True
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
                "tax_exemption_reason": self.l10npt_vat_exempt_reason.code or "M00",
            },
            "proprietary_uid": self.name,
        }
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

    def _update_invoicexpress_status(self, result):
        vals = {
            "invoicexpress_id": result.get("id"),
            "invoicexpress_permalink": result.get("permalink"),
        }
        self.update(vals)
        inv_xpress_link = _(
            " <a class='btn btn-info mr-2' href={}>View Document</a>"
        ).format(result.get("permalink"))
        msg = _(
            "InvoiceXpress record has been created for this invoice:"
            "<ul><li>InvoiceXpress Id: {inv_xpress_id}</li>"
            "<li>{inv_xpress_link}</li></ul>"
        ).format(inv_xpress_id=result.get("id"), inv_xpress_link=inv_xpress_link)
        self.message_post(body=msg)

    def action_create_invoicexpress_invoice(self):
        InvoiceXpress = self.env["account.invoicexpress"]
        for invoice in self.filtered(lambda x: not x.invoicexpress_id):
            doctype = invoice._get_invoicexpress_doctype()
            payload = invoice._prepare_invoicexpress_vals()
            response = InvoiceXpress.call(
                "{}.json".format(doctype), "POST", payload=payload
            )
            values = response.json().get("invoice")
            if values:
                invoice._update_invoicexpress_status(values)
                InvoiceXpress.call(
                    "{}/{}/change-state.json".format(doctype, values["id"]),
                    "PUT",
                    payload={"invoice": {"state": "finalized"}},
                )

    def _prepare_invoicexpress_email_vals(self):
        self.ensure_one()
        ICPSudo = self.env["ir.config_parameter"].sudo()
        eval_context = {"self": self}
        email_to = safe_eval(
            ICPSudo.get_param(
                "invoicexpress.invoice_email_to", "self.partner_id.email"
            ),
            eval_context,
        )
        email_cc = safe_eval(
            ICPSudo.get_param("invoicexpress.invoice_email_cc", ""), eval_context
        )
        if not email_to:
            raise exceptions.UserError(
                _("Kindly Configure the customer email address.")
            )
        email_data = {
            "message": {
                "client": {"email": email_to, "save": "0"},
                "cc": email_cc,
                "subject": _("Invoice from InvoiceXpress"),
                "body": _("InvoiceXpress Documents"),
            }
        }
        return email_data

    def action_send_invoicexpress_email(self):
        InvoiceXpress = self.env["account.invoicexpress"]
        for invoice in self.filtered(lambda x: not x.invoicexpress_id):
            endpoint = "invoices/{}/email-document.json".format(
                invoice.invoicexpress_id
            )
            payload = invoice._prepare_invoicexpress_email_vals()
            InvoiceXpress.call(endpoint, "PUT", payload=payload)
            msg = "InvoiceXpress document has been sent successfully"
            invoice.message_post(body=msg)
