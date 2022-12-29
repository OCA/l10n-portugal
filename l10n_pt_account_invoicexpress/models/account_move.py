# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import uuid

from odoo import _, api, exceptions, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.depends("restrict_mode_hash_table", "state")
    def _compute_show_reset_to_draft_button(self):
        super()._compute_show_reset_to_draft_button()
        # InvoiceXpress generated invoices can't be set to Draft
        self.filtered("invoicexpress_id").write({"show_reset_to_draft_button": False})
        return

    @api.depends("move_type", "journal_id.use_invoicexpress")
    def _compute_can_invoicexpress(self):
        for invoice in self:
            invoice.can_invoicexpress = (
                invoice.journal_id.use_invoicexpress and invoice.is_sale_document()
            )

    @api.depends("can_invoicexpress", "company_id.invoicexpress_template_id")
    def _compute_can_invoicexpress_email(self):
        for invoice in self:
            invoice.can_invoicexpress_email = (
                invoice.can_invoicexpress
                and invoice.company_id.invoicexpress_template_id
            )

    @api.depends("move_type", "journal_id", "partner_shipping_id")
    def _compute_invoicexpress_doc_type(self):
        """
        The type of document to create: invoices, invoice_receipts,
        simplified_invoices, vat_moss_invoices, credit_notes or debit_notes.
        """
        invoices = self.filtered("journal_id.use_invoicexpress")
        for invoice in invoices:
            doctype = invoice.journal_id.invoicexpress_doc_type
            europe = self.env.ref("base.europe")
            country = invoice.partner_shipping_id.country_id
            is_eu = country and country.code != "PT" and country in europe.country_ids
            if not doctype or doctype == "none":
                res = None
            elif invoice.move_type == "out_refund":
                res = "vat_moss_credit_note" if is_eu else "credit_note"
            else:
                res = "vat_moss_invoice" if is_eu else doctype
            invoice.invoicexpress_doc_type = res

    journal_type = fields.Selection(
        related="journal_id.type", string="Journal Type", readonly=True
    )
    invoicexpress_id = fields.Char("InvoiceXpress ID", copy=False, readonly=True)
    invoicexpress_permalink = fields.Char(
        "InvoiceXpress Doc Link", copy=False, readonly=True
    )
    can_invoicexpress = fields.Boolean(compute="_compute_can_invoicexpress")
    can_invoicexpress_email = fields.Boolean(compute="_compute_can_invoicexpress_email")

    invoicexpress_doc_type = fields.Selection(
        [
            ("invoice", "Invoice"),
            ("invoice_receipt", "Invoice and Receipt"),
            ("simplified_invoice", "Simplified Invoice"),
            ("vat_moss_invoice", "Europe VAT MOSS Invoice"),
            ("vat_moss_credit_note", "Europe VAT MOSS Credit Note"),
            ("debit_note", "Debit Note"),
            ("credit_note", "Credit Note"),
        ],
        compute="_compute_invoicexpress_doc_type",
        store=True,
        readonly=False,
        copy=False,
        help="Select the type of legal invoice document"
        " to be created by InvoiceXpress."
        " If unset, InvoiceXpress will not be used.",
    )

    @api.constrains("journal_id", "company_id")
    def _check_invoicexpress_doctype_config(self):
        """
        Ensure Journal configuration was not forgotten.
        """
        sale_invoices = self.filtered(lambda x: x.journal_id.type == "sale")
        for invoice in sale_invoices:
            journal_doctype = invoice.journal_id.invoicexpress_doc_type
            has_invoicexpress = invoice.company_id.has_invoicexpress
            if not journal_doctype and has_invoicexpress:
                raise exceptions.UserError(
                    _(
                        "Journal %s is missing the InvoiceXpress"
                        " document type configuration!"
                    )
                    % invoice.journal_id.display_name
                )

    @api.model
    def _get_invoicexpress_prefix(self, doctype):
        return {
            "invoice": "FT",
            "invoice_receipt": "FR",
            "simplified_invoice": "FS",
            "vat_moss_invoice": "FVM",
            # vat_moss_credit_note does not have a prefix!
            "credit_note": "NC",
            "debit_note": "ND",
        }.get(doctype)

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
                    "description": line._get_invoicexpress_descr(),
                    "unit_price": line.price_unit,
                    "quantity": line.quantity,
                    "discount": line.discount,
                    "tax": tax_detail,
                }
            )
        return items

    def _get_invoicexpress_partner(self):
        # Hook to customize the "client" values to use
        return self.commercial_partner_id

    def _prepare_invoicexpress_vals(self):
        self.ensure_one()
        if not self.invoice_date and self.invoice_date_due:
            raise exceptions.UserError(
                _("Kindly add the invoice date and invoice due date.")
            )
        customer = self._get_invoicexpress_partner()
        customer_vals = customer.set_invoicexpress_contact()
        items = self._prepare_invoicexpress_lines()
        proprietary_uid = "ODOO" + str(uuid.uuid4()).replace("-", "")
        invoice_data = {
            "invoice": {
                "date": self.invoice_date.strftime("%d/%m/%Y"),
                "due_date": self.invoice_date_due.strftime("%d/%m/%Y"),
                "reference": self.ref or "",
                "client": customer_vals,
                "observations": self.narration or "",
                "items": items,
            },
            "proprietary_uid": proprietary_uid,
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
            invoice_data["invoice"].update(
                {"currency_code": self.currency_id.name, "rate": str(currency_rate)}
            )
        doctype = self.invoicexpress_doc_type
        if doctype in ("credit_note", "debit_note"):
            owner_invoice_num = self.reversed_entry_id.invoicexpress_id
            if owner_invoice_num:
                invoice_data["invoice"]["owner_invoice_id"] = owner_invoice_num
        return invoice_data

    def _update_invoicexpress_status(self):
        inv_xpress_link_name = _("View Document")
        inv_xpress_link = (
            "<a class='btn btn-info mr-2' target='new' href={}>{}</a>"
        ).format(self.invoicexpress_permalink, inv_xpress_link_name)
        msg = _(
            "InvoiceXpress record has been created for this invoice:"
            "<ul><li>InvoiceXpress Id: {inv_xpress_id}</li>"
            "<li>{inv_xpress_link}</li></ul>"
        ).format(inv_xpress_id=self.invoicexpress_id, inv_xpress_link=inv_xpress_link)
        self.message_post(body=msg)

    def action_create_invoicexpress_invoice(self):
        InvoiceXpress = self.env["account.invoicexpress"]
        for invoice in self.filtered("can_invoicexpress"):
            doctype = invoice.invoicexpress_doc_type
            if not doctype:
                raise exceptions.UserError(
                    _("Invoice is missing the InvoiceXpress document type!")
                )
            payload = invoice._prepare_invoicexpress_vals()
            response = InvoiceXpress.call(
                invoice.company_id, "{}s.json".format(doctype), "POST", payload=payload
            ).json()
            values = response.get(doctype)
            if not values:
                raise exceptions.UserError(
                    _("Something went wrong: the InvoiceXpress response looks empty.")
                )
            invoice.invoicexpress_id = values.get("id")
            invoice.invoicexpress_permalink = values.get("permalink")
            response1 = InvoiceXpress.call(
                invoice.company_id,
                "{}s/{}/change-state.json".format(doctype, invoice.invoicexpress_id),
                "PUT",
                payload={"invoice": {"state": "finalized"}},
                raise_errors=True,
            ).json()
            values1 = response1.get(doctype)
            seqnum = values1 and values1.get("inverted_sequence_number")
            if not seqnum:
                raise exceptions.UserError(
                    _(
                        "Something went wrong: the InvoiceXpress response"
                        " is missing a sequence number."
                    )
                )
            prefix = self._get_invoicexpress_prefix(doctype)
            invx_number = "%s %s" % (prefix, seqnum) if prefix else seqnum
            if invoice.payment_reference == invoice.name:
                invoice.payment_reference = invx_number
            invoice.name = invx_number
            invoice._update_invoicexpress_status()

    def _prepare_invoicexpress_email_vals(self, ignore_no_config=False):
        self.ensure_one()
        template_id = self.company_id.invoicexpress_template_id
        values = template_id.generate_email(
            self.id, ["subject", "body_html", "email_to", "email_cc"]
        )
        if not template_id and not ignore_no_config:
            raise exceptions.UserError(
                _(
                    "Please configure the InvoiceXpress email template"
                    " at Settings > General Setting, InvoiceXpress section"
                )
            )
        if not values.get("email_to") and not ignore_no_config:
            raise exceptions.UserError(_("No address to send invoice email to."))
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

    def action_send_invoicexpress_email(self, ignore_no_config=False):
        InvoiceXpress = self.env["account.invoicexpress"]
        for invoice in self.filtered("can_invoicexpress_email"):
            if not invoice.invoicexpress_id:
                raise exceptions.UserError(
                    _("Invoice %s is not registered in InvoiceXpress yet.")
                    % invoice.name
                )
            doctype = invoice.invoicexpress_doc_type
            endpoint = "{}s/{}/email-document.json".format(
                doctype, invoice.invoicexpress_id
            )
            payload = invoice._prepare_invoicexpress_email_vals(ignore_no_config)
            if payload:
                InvoiceXpress.call(invoice.company_id, endpoint, "PUT", payload=payload)
                msg = _(
                    "Email sent by InvoiceXpress:<ul><li>To: {}</li><li>Cc: {}</li></ul>"
                ).format(
                    payload["message"]["client"]["email"],
                    payload["message"]["cc"] or _("None"),
                )
                invoice.message_post(body=msg)

    def _post(self, soft=False):
        res = super()._post(soft=soft)
        for invoice in self:
            if not invoice.invoicexpress_id:
                invoice._check_invoicexpress_doctype_config()
                invoice.action_create_invoicexpress_invoice()
                invoice.action_send_invoicexpress_email(ignore_no_config=True)
        return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_invoicexpress_descr(self):
        """
        Remove Odoo product code from description,
        since it is already presented in a the Code column
        """
        res = self.name
        ref = self.product_id.default_code
        prefix = "[%s] " % ref
        if ref and self.name.startswith(prefix):
            res = self.name[len(prefix) :]
        return res
