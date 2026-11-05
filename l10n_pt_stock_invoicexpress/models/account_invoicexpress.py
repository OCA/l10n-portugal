# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import exceptions, models


class InvoiceXpress(models.AbstractModel):
    _inherit = "account.invoicexpress"

    # Transport document support: pickings use the transports/shippings/
    # devolutions endpoints, configured on the picking type instead of
    # the journal.

    def is_available(self, config):
        if config._name != "stock.picking.type":
            return super().is_available(config)
        return bool(
            config.company_id.has_invoicexpress
            and config.invoicexpress_doc_type
            and config.invoicexpress_doc_type != "none"
        )

    def can_email_document(self, config):
        if config._name != "stock.picking.type":
            return super().can_email_document(config)
        return bool(config.company_id.invoicexpress_delivery_template_id)

    def get_document_type(self, document):
        if document._name != "stock.picking":
            return super().get_document_type(document)
        # Devolution auto-detection is not supported yet (TODO from 19.0)
        return document.picking_type_id.invoicexpress_doc_type

    def get_doc_prefix(self, doc_type):
        return super().get_doc_prefix(doc_type) or {
            "transport": "GT",
            "shipping": "GR",
            "devolution": "GD",
        }.get(doc_type)

    def create_document(self, document):
        if document._name != "stock.picking":
            return super().create_document(document)
        picking = document
        if picking.l10npt_has_tax_exempt_lines and not picking.l10npt_vat_exempt_reason:
            raise exceptions.UserError(
                self.env._("A tax exemption reason must be provided.")
            )
        payload = picking._prepare_invoicexpress_vals()
        doctype = picking.l10n_pt_doc_type
        response = self.call(
            picking.company_id, f"{doctype}s.json", "POST", payload=payload
        )
        values = response.json().get(doctype)
        if not values:
            raise exceptions.UserError(
                self.env._(
                    "Something went wrong: the InvoiceXpress response looks empty."
                )
            )
        picking.l10n_pt_doc_id = values.get("id")
        picking.l10n_pt_doc_permalink = values.get("permalink")
        response1 = self.call(
            picking.company_id,
            f"{doctype}s/{values['id']}/change-state.json",
            "PUT",
            payload={doctype: {"state": "finalized"}},
        )
        values1 = response1.json().get(doctype)
        seqnum = values1 and values1.get("inverted_sequence_number")
        if not seqnum:
            raise exceptions.UserError(
                self.env._(
                    "Something went wrong: the InvoiceXpress response"
                    " is missing a sequence number."
                )
            )
        prefix = self.get_doc_prefix(doctype)
        picking.l10n_pt_doc_number = f"{prefix} {seqnum}" if prefix else seqnum
        picking._l10n_pt_doc_post_message(self._description)

    def email_document(self, document, ignore_no_config=False):
        if document._name != "stock.picking":
            return super().email_document(document, ignore_no_config)
        picking = document
        doctype = picking.l10n_pt_doc_type
        endpoint = f"{doctype}s/{picking.l10n_pt_doc_id}/email-document.json"
        payload = picking._prepare_invoicexpress_email_vals(ignore_no_config)
        if payload:
            self.call(picking.company_id, endpoint, "PUT", payload=payload)
            picking.message_post(
                body=self.env._(
                    "Email sent by InvoiceXpress:"
                    "<ul><li>To: %(email)s</li><li>Cc: %(cc)s</li></ul>",
                    email=payload["message"]["client"]["email"],
                    cc=payload["message"].get("cc", ""),
                )
            )
