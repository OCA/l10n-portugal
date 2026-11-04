# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

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

    def _compute_l10n_pt_doc_email_enabled(self):
        # Providers override to signal email sending is configured
        for move in self:
            move.l10n_pt_doc_email_enabled = move.l10n_pt_doc_enabled

    @api.depends("restrict_mode_hash_table", "state")
    def _compute_show_reset_to_draft_button(self):
        res = super()._compute_show_reset_to_draft_button()
        # Provider generated documents can't be set to Draft
        self.filtered("l10n_pt_doc_id").write({"show_reset_to_draft_button": False})
        return res

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        for doc in self:
            if doc.l10n_pt_doc_enabled and not doc.l10n_pt_doc_id:
                doc.l10n_pt_create_document()
                doc.action_l10n_pt_send_email(ignore_no_config=True)
        return res

    def _track_subtype(self, init_values):
        res = super()._track_subtype(init_values)
        if "payment_state" in init_values and self.payment_state == "paid":
            for doc in self.filtered("l10n_pt_doc_id"):
                doc._l10n_pt_provider().settle_document(doc)
        return res
