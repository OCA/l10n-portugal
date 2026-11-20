# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import uuid

from odoo import api, exceptions, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    invoicexpress_tax_exemption = fields.Char(
        string="InvoiceXpress VAT Exemption",
        compute="_compute_invoicexpress_tax_exemption",
    )

    @api.depends(
        "invoice_line_ids.display_type",
        "invoice_line_ids.tax_ids.amount",
        "invoice_line_ids.tax_ids.amount_type",
        "invoice_line_ids.tax_ids.l10n_pt_tax_exemption_reason",
    )
    def _compute_invoicexpress_tax_exemption(self):
        for move in self:
            codes = move._get_invoicexpress_exemption_codes()
            move.invoicexpress_tax_exemption = codes[0] if len(codes) == 1 else False

    def _get_invoicexpress_exemption_codes(self):
        taxes = self._get_invoicexpress_product_lines().tax_ids.filtered(
            lambda tax: tax.amount_type != "group" and tax.amount == 0
        )
        return sorted(set(taxes.mapped("l10n_pt_tax_exemption_reason")) - {False})

    def _get_invoicexpress_product_lines(self):
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )

    @api.depends(
        "l10n_pt_doc_provider", "move_type", "journal_id.invoicexpress_doc_type"
    )
    def _compute_l10n_pt_doc_type(self):
        return super()._compute_l10n_pt_doc_type()

    @api.constrains("journal_id", "company_id")
    def _check_invoicexpress_doctype_config(self):
        # Ensure Journal configuration was not forgotten.
        for invoice in self.filtered(lambda x: x.journal_id.type == "sale"):
            if (
                invoice.journal_id.l10n_pt_doc_provider == "invoicexpress"
                and not invoice.journal_id.invoicexpress_doc_type
            ):
                raise exceptions.UserError(
                    self.env._(
                        "Journal %(journal)s is missing the InvoiceXpress"
                        " document type configuration!",
                        journal=invoice.journal_id.display_name,
                    )
                )

    def _prepare_invoicexpress_lines(self):
        # FIXME: set user lang, based on country?
        lines = self._get_invoicexpress_product_lines()
        # Ensure Taxes are created on InvoiceXpress
        lines.mapped("tax_ids").action_invoicexpress_tax_create()
        items = []
        for line in lines:
            tax = line.tax_ids
            tax_detail = {"name": tax.name, "value": tax.amount}
            # Because InvoiceXpress expects unit_price in EUR,
            # check if we need to convert
            # line currency to company currency
            # (company should use EUR as default currency)
            if line.currency_id == line.company_id.currency_id:
                price_unit = line.price_unit
            else:
                price_unit = line.currency_id._convert(
                    line.price_unit,
                    line.company_id.currency_id,
                    line.company_id,
                    line.move_id.invoice_date
                    or line.move_id.date
                    or fields.Date.context_today(line),
                )
            items.append(
                {
                    "name": line.product_id.default_code
                    or line.product_id.display_name,
                    "description": line._get_invoicexpress_descr(),
                    "unit_price": price_unit,
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
        exempt_code = self._validate_invoicexpress_tax_exemption()
        if not self.invoice_date and self.invoice_date_due:
            raise exceptions.UserError(
                self.env._("Kindly add the invoice date and invoice due date.")
            )
        customer = self._get_invoicexpress_partner()
        customer_vals = customer.set_invoicexpress_contact(company=self.company_id)
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
        doctype = self.l10n_pt_doc_type
        if doctype in ("credit_note", "debit_note"):
            # For standalone credit notes (invoices created outside InvoiceXpress)
            # Use ref field for it contains the invoice series/number
            if self.ref and not self.reversed_entry_id.l10n_pt_doc_id:
                invoice_data["raw_owner_invoice"] = self.ref
            # For credit notes referencing invoices created in InvoiceXpress
            else:
                owner_invoice_num = self.reversed_entry_id.l10n_pt_doc_id
                if owner_invoice_num:
                    invoice_data["invoice"]["owner_invoice_id"] = owner_invoice_num
        return invoice_data

    def _validate_invoicexpress_tax_exemption(self):
        codes = self._get_invoicexpress_exemption_codes()
        if len(codes) > 1:
            raise exceptions.UserError(
                self.env._(
                    "InvoiceXpress accepts one VAT exemption reason per document. "
                    "Split this invoice: its lines use %(codes)s.",
                    codes=", ".join(codes),
                )
            )
        for line in self._get_invoicexpress_product_lines():
            tax = line.tax_ids
            if len(tax) != 1 or tax.amount_type == "group":
                raise exceptions.UserError(
                    self.env._(
                        "InvoiceXpress requires one tax per invoice line. "
                        "Set a single tax on %(line)s.",
                        line=line.name,
                    )
                )
            if tax.amount == 0 and not tax.l10n_pt_tax_exemption_reason:
                raise exceptions.UserError(
                    self.env._(
                        "Set a VAT exemption reason on the zero-rate tax %(tax)s "
                        "before sending this invoice to InvoiceXpress.",
                        tax=tax.display_name,
                    )
                )
        return codes[0] if codes else False

    def _prepare_invoicexpress_email_vals(self, ignore_no_config=False):
        self.ensure_one()
        template_id = self.company_id.invoicexpress_template_id
        if not template_id and not ignore_no_config:
            raise exceptions.UserError(
                self.env._(
                    "Please configure the InvoiceXpress email template"
                    " at Settings > General Setting, InvoiceXpress section"
                )
            )
        values = template_id._generate_template(
            [self.id], ["subject", "body_html", "email_to", "email_cc"]
        )[self.id]
        if not values.get("email_to") and not ignore_no_config:
            raise exceptions.UserError(
                self.env._("No address to send invoice email to.")
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


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_invoicexpress_descr(self):
        """
        Remove Odoo product code from description,
        since it is already presented in a the Code column
        """
        res = self.name
        ref = self.product_id.default_code
        prefix = f"[{ref}] "
        if ref and self.name.startswith(prefix):
            res = self.name[len(prefix) :]
        return res
