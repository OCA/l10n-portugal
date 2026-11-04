# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64

from odoo import api, fields, models


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ("account.move", "l10n_pt.invoice.document.mixin")

    journal_type = fields.Selection(
        related="journal_id.type", string="Journal Type", readonly=True
    )
    l10n_pt_doc_email_enabled = fields.Boolean(
        compute="_compute_l10n_pt_doc_email_enabled"
    )

    @api.depends("journal_id.l10n_pt_doc_provider", "move_type")
    def _compute_l10n_pt_doc_provider(self):
        for move in self:
            move.l10n_pt_doc_provider = (
                move.is_sale_document() and move.journal_id.l10n_pt_doc_provider
            )

    @api.depends("move_type", "journal_id.l10n_pt_doc_enabled")
    def _compute_l10n_pt_doc_enabled(self):
        for move in self:
            move.l10n_pt_doc_enabled = (
                move.journal_id.l10n_pt_doc_enabled and move.is_sale_document()
            )

    @api.depends("l10n_pt_doc_enabled", "company_id")
    def _compute_l10n_pt_doc_email_enabled(self):
        for move in self:
            provider = move._l10n_pt_provider()
            move.l10n_pt_doc_email_enabled = bool(
                move.l10n_pt_doc_enabled
                and provider
                and provider.can_email_document(move.journal_id)
            )

    @api.depends("restrict_mode_hash_table", "state")
    def _compute_show_reset_to_draft_button(self):
        res = super()._compute_show_reset_to_draft_button()
        # Provider generated documents can't be set to Draft
        self.filtered("l10n_pt_doc_id").write({"show_reset_to_draft_button": False})
        return res

    def action_l10n_pt_view_document(self):
        # Fall back to the synced provider PDF
        # when the provider has no public document link.
        action = super().action_l10n_pt_view_document()
        if not action and self.invoice_pdf_report_id:
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{self.invoice_pdf_report_id.id}",
                "target": "new",
            }
        return action

    def _l10n_pt_sync_document_pdf(self):
        # Store the provider's PDF as the invoice's official document,
        # so the standard Send flow mails the legal document.
        for doc in self.filtered("l10n_pt_doc_id"):
            provider = doc._l10n_pt_provider()
            pdf = provider and provider.get_document_pdf(doc)
            if pdf:
                doc.invoice_pdf_report_id = self.env["ir.attachment"].create(
                    {
                        "name": "%s.pdf"
                        % (doc.l10n_pt_doc_number or doc.l10n_pt_doc_id),
                        "res_model": "account.move",
                        "res_id": doc.id,
                        "type": "binary",
                        "mimetype": "application/pdf",
                        "datas": base64.b64encode(pdf),
                    }
                )

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        for doc in self:
            if doc.l10n_pt_doc_enabled and not doc.l10n_pt_doc_id:
                doc.l10n_pt_create_document()
                doc._l10n_pt_sync_document_pdf()
        return res

    def _track_subtype(self, init_values):
        res = super()._track_subtype(init_values)
        if "payment_state" in init_values and self.payment_state == "paid":
            for doc in self.filtered("l10n_pt_doc_id"):
                provider = doc._l10n_pt_provider()
                if provider:
                    provider.settle_document(doc)
        return res
