# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, exceptions, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.depends("l10n_pt_doc_provider", "move_type", "journal_id.moloni_doc_type")
    def _compute_l10n_pt_doc_type(self):
        return super()._compute_l10n_pt_doc_type()

    @api.constrains("journal_id", "company_id")
    def _check_moloni_doctype_config(self):
        # Ensure Journal configuration was not forgotten.
        for invoice in self.filtered(lambda x: x.journal_id.type == "sale"):
            if (
                invoice.journal_id.l10n_pt_doc_provider == "moloni"
                and not invoice.journal_id.moloni_doc_type
            ):
                raise exceptions.UserError(
                    self.env._(
                        "Journal %(journal)s is missing the Moloni"
                        " document type configuration!",
                        journal=invoice.journal_id.display_name,
                    )
                )

    def _prepare_moloni_lines(self):
        lines = self.invoice_line_ids.filtered(
            lambda x: x.display_type not in ("line_section", "line_note")
        )
        items = []
        for line in lines:
            tax = line.tax_ids[:1]
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
            item = {
                "name": (line.product_id.display_name or line.name or "")[:30],
                "summary": line._get_invoicexpress_descr()
                if hasattr(line, "_get_invoicexpress_descr")
                else line.name,
                "qty": line.quantity,
                "price": price_unit,
                "discount": line.discount,
                "order": len(items) + 1,
            }
            if tax:
                item["taxes"] = [
                    {
                        "value": tax.amount,
                        "order": 1,
                    }
                ]
            else:
                item["taxes"] = []
            if not tax.amount:
                exempt = (
                    tax.l10n_pt_tax_exemption_reason or self.l10npt_vat_exempt_reason
                )
                item["exemption_reason"] = exempt and exempt.code or ""
            items.append(item)
        return items

    def _prepare_moloni_vals(self):
        self.ensure_one()
        customer = self.commercial_partner_id
        customer_id = customer.set_moloni_contact(company=self.company_id)
        document = {
            "company_id": self.company_id.moloni_company_id,
            "customer_id": customer_id,
            "date": self.invoice_date.strftime("%Y-%m-%d"),
            "expiration_date": (self.invoice_date_due or self.invoice_date).strftime(
                "%Y-%m-%d"
            ),
            "status": 1,  # finalized
            "our_reference": self.ref or "",
            "notes": self.narration or "",
            "products": self._prepare_moloni_lines(),
        }
        if self.move_type == "out_refund" and self.reversed_entry_id.l10n_pt_doc_id:
            document["associated_documents"] = [
                {"associated_id": self.reversed_entry_id.l10n_pt_doc_id}
            ]
        return document
