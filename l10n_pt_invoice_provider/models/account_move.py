# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, exceptions, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ("account.move", "l10n_pt.invoice.document.mixin")

    journal_type = fields.Selection(
        related="journal_id.type", string="Journal Type", readonly=True
    )
    l10n_pt_doc_email_enabled = fields.Boolean(
        compute="_compute_l10n_pt_doc_email_enabled"
    )
    # Snapshot fields: provider and type are set at creation (or by an explicit
    # journal-provider refresh) instead of being recomputed from the journal.
    l10n_pt_doc_provider_id = fields.Many2one(compute=None)
    l10n_pt_doc_type = fields.Char(compute=None)

    @api.depends("move_type", "journal_id", "l10n_pt_doc_provider_id")
    def _compute_l10n_pt_doc_enabled(self):
        for move in self:
            provider = move._l10n_pt_provider()
            move.l10n_pt_doc_enabled = (
                move.is_sale_document()
                and provider is not None
                and bool(provider.is_available(move.journal_id))
            )

    def _compute_l10n_pt_doc_email_enabled(self):
        for move in self:
            provider = move._l10n_pt_provider()
            move.l10n_pt_doc_email_enabled = bool(
                move.l10n_pt_doc_enabled
                and provider is not None
                and provider.can_email_document(move.journal_id)
            )

    @api.depends("restrict_mode_hash_table", "state")
    def _compute_show_reset_to_draft_button(self):
        res = super()._compute_show_reset_to_draft_button()
        # Provider generated documents can't be set to Draft
        self.filtered("l10n_pt_doc_id").write({"show_reset_to_draft_button": False})
        return res

    def action_l10n_pt_view_document(self):
        """Open the provider's document page, or its PDF if there is no link.

        This is a shortcut for viewing the issued document, separate from
        Odoo's Print action. Fetch the provider PDF on demand if needed.
        """
        action = super().action_l10n_pt_view_document()
        attachment = (
            self._l10n_pt_ensure_document_pdf()
            if not action and self._l10n_pt_requires_provider_pdf()
            else self.invoice_pdf_report_id
        )
        if not action and attachment:
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{attachment.id}",
                "target": "new",
            }
        return action

    def _l10n_pt_requires_provider_pdf(self):
        self.ensure_one()
        return (
            self.state == "posted"
            and self.is_sale_document()
            and bool(self.l10n_pt_doc_provider_id or self.l10n_pt_doc_id)
        )

    def _l10n_pt_print_as_proforma(self):
        self.ensure_one()
        return (
            self.state == "posted"
            and self.move_type == "out_invoice"
            and self.journal_id.country_code == "PT"
            and not self._l10n_pt_requires_provider_pdf()
        )

    def _l10n_pt_ensure_document_pdf(self):
        self.ensure_one()
        if not self.l10n_pt_doc_id:
            raise exceptions.UserError(
                self.env._(
                    "The legal document has not been issued. "
                    "Issue it before printing or sending it."
                )
            )
        if attachment := self._l10n_pt_get_cached_document_pdf():
            return attachment
        provider = self._l10n_pt_provider()
        if provider is None and self.l10n_pt_doc_provider_id:
            raise exceptions.UserError(
                self.env._(
                    "The legal document provider %(code)s is not installed. "
                    "Reinstall it to retrieve the PDF.",
                    code=self.l10n_pt_doc_provider_id.code,
                )
            )
        try:
            content = provider.get_document_pdf(self) if provider is not None else None
        except OSError as error:
            raise exceptions.UserError(
                self.env._("The legal document PDF is unavailable. Try again later.")
            ) from error
        if not isinstance(content, bytes) or not content.startswith(b"%PDF-"):
            raise exceptions.UserError(
                self.env._("The legal document PDF is unavailable. Try again later.")
            )
        # Keep the old file as a regular attachment, not the official invoice PDF.
        self.invoice_pdf_report_id.write({"res_field": False})
        attachment = self.env["ir.attachment"].create(
            {
                "name": "%s.pdf" % (self.l10n_pt_doc_number or self.l10n_pt_doc_id),
                "res_model": self._name,
                "res_id": self.id,
                "res_field": "invoice_pdf_report_file",
                "mimetype": "application/pdf",
                "raw": content,
                "l10n_pt_doc_pdf_provider": self.l10n_pt_doc_provider_id.code,
            }
        )
        self.invalidate_recordset(["invoice_pdf_report_id", "invoice_pdf_report_file"])
        return attachment

    def _l10n_pt_get_cached_document_pdf(self):
        self.ensure_one()
        attachment = self.invoice_pdf_report_id
        if (
            self.l10n_pt_doc_provider_id
            and attachment.l10n_pt_doc_pdf_provider == self.l10n_pt_doc_provider_id.code
        ):
            return attachment
        return self.env["ir.attachment"]

    def _get_invoice_legal_documents(self, filetype, allow_fallback=False):
        if filetype == "pdf" and self._l10n_pt_requires_provider_pdf():
            self._l10n_pt_ensure_document_pdf()
        return super()._get_invoice_legal_documents(
            filetype, allow_fallback=allow_fallback
        )

    def _get_invoice_legal_documents_all(self, allow_fallback=False):
        if self._l10n_pt_requires_provider_pdf():
            self._l10n_pt_ensure_document_pdf()
        return super()._get_invoice_legal_documents_all(allow_fallback=allow_fallback)

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        # Snapshot the journal defaults after super(): core resolves the
        # default journal during create, so journal_id is only final here.
        for move, vals in zip(moves, vals_list, strict=True):
            if not move.is_sale_document():
                continue
            context = self.env.context
            # Forms serialize empty provider fields, so only truthy values count
            # as explicit overrides; falsy entries still take the journal default.
            if (
                not vals.get("l10n_pt_doc_provider_id")
                and "default_l10n_pt_doc_provider_id" not in context
            ):
                move.l10n_pt_doc_provider_id = move.journal_id.l10n_pt_doc_provider_id
            if (
                not vals.get("l10n_pt_doc_type")
                and "default_l10n_pt_doc_type" not in context
                and (provider := move._l10n_pt_provider()) is not None
            ):
                move.l10n_pt_doc_type = provider.get_document_type(move)
        return moves

    def button_draft(self):
        # Provider documents are final; invoices linked to one
        # cannot go back to draft, whatever the UI shows.
        if self.filtered("l10n_pt_doc_id"):
            raise exceptions.UserError(
                self.env._("Invoices with a legal document cannot be reset to draft.")
            )
        return super().button_draft()

    def _post(self, soft=True):
        # The stored provider must match the journal's when a move is actually
        # posted, before any provider request; soft posting only checks moves
        # that are due, not future-dated ones queued for later.
        today = fields.Date.context_today(self) if soft else None
        for move in self:
            if not (
                move.state == "draft"
                and move.is_sale_document()
                and (not soft or not move.date or move.date <= today)
            ):
                continue
            if move.l10n_pt_doc_provider_id != move.journal_id.l10n_pt_doc_provider_id:
                raise exceptions.UserError(
                    self.env._(
                        "The legal document provider on %(invoice)s does not match "
                        "the provider configured on journal %(journal)s.",
                        invoice=move.display_name,
                        journal=move.journal_id.display_name,
                    )
                )
            if (
                move.l10n_pt_doc_provider_id
                and not move.l10n_pt_doc_id
                and move._l10n_pt_provider() is None
            ):
                raise exceptions.UserError(
                    self.env._(
                        "The legal document provider %(code)s is not installed.",
                        code=move.l10n_pt_doc_provider_id.code,
                    )
                )
        res = super()._post(soft=soft)
        # Only the records actually posted get a legal document:
        # scheduled invoices are skipped until they post for real.
        for doc in res:
            if doc.l10n_pt_doc_enabled and not doc.l10n_pt_doc_id:
                doc.l10n_pt_create_document()
                doc._l10n_pt_sync_document_pdf()
        return res

    def _l10n_pt_sync_document_pdf(self):
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self._l10n_pt_ensure_document_pdf()
        except exceptions.UserError as error:
            # Issuance succeeded; Print or Send can retry PDF retrieval.
            _logger.info(
                "Provider PDF unavailable for %s: %s", self.display_name, error
            )

    def _track_subtype(self, init_values):
        res = super()._track_subtype(init_values)
        if "payment_state" in init_values and self.payment_state == "paid":
            for doc in self.filtered("l10n_pt_doc_id"):
                provider = doc._l10n_pt_provider()
                if provider is not None:
                    provider.settle_document(doc)
        return res
