# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.exceptions import UserError


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _get_invoice_extra_attachments(self, move):
        attachments = super()._get_invoice_extra_attachments(move)
        if (
            move._requires_invoicexpress_pdf()
            and not move._get_cached_invoicexpress_pdf()
        ):
            return attachments - move.invoice_pdf_report_id
        return attachments

    @api.model
    def _hook_invoice_document_before_pdf_report_render(self, invoice, invoice_data):
        super()._hook_invoice_document_before_pdf_report_render(invoice, invoice_data)
        if invoice_data.get("error") or not invoice._requires_invoicexpress_pdf():
            return
        old_pdf = invoice.invoice_pdf_report_id
        try:
            attachment = invoice._ensure_invoicexpress_pdf()
        except UserError as error:
            invoice_data["error"] = {"error_title": str(error), "retry": True}
            invoice_data["error_but_continue"] = False
        else:
            if (
                old_pdf
                and old_pdf != attachment
                and "mail_attachments_widget" in invoice_data
            ):
                invoice_data["mail_attachments_widget"] = [
                    item
                    for item in invoice_data["mail_attachments_widget"]
                    if str(item.get("id")) != str(old_pdf.id) or item.get("manual")
                ]

    @api.model
    def _generate_invoice_fallback_documents(self, invoices_data):
        return super()._generate_invoice_fallback_documents(
            {
                move: data
                for move, data in invoices_data.items()
                if not move._requires_invoicexpress_pdf()
            }
        )
