# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_pt_doc_provider_id = fields.Many2one(
        "l10n_pt.invoice.provider.record",
        string="Legal Document Provider",
        ondelete="restrict",
        help="Legal document service used for documents on this journal.",
    )
    l10n_pt_doc_enabled = fields.Boolean(
        compute="_compute_l10n_pt_doc_enabled",
        help="Set when the selected provider is configured on the company.",
    )

    @api.depends("l10n_pt_doc_provider_id", "company_id")
    def _compute_l10n_pt_doc_enabled(self):
        Provider = self.env["l10n_pt.invoice.provider"]
        for journal in self:
            provider = Provider._get_provider(journal.l10n_pt_doc_provider_id.code)
            journal.l10n_pt_doc_enabled = bool(
                provider is not None and provider.is_available(journal)
            )

    def write(self, vals):
        # Provider changes refresh unissued draft documents on the journal;
        # posted, cancelled and issued documents keep their stored values.
        previous = (
            {journal.id: journal.l10n_pt_doc_provider_id.id for journal in self}
            if "l10n_pt_doc_provider_id" in vals
            else {}
        )
        res = super().write(vals)
        for journal in self:
            if (
                journal.id not in previous
                or previous[journal.id] == journal.l10n_pt_doc_provider_id.id
            ):
                continue
            moves = self.env["account.move"].search(
                [
                    ("journal_id", "=", journal.id),
                    ("state", "=", "draft"),
                    ("move_type", "in", ("out_invoice", "out_refund")),
                    ("l10n_pt_doc_id", "=", False),
                    (
                        "l10n_pt_doc_provider_id",
                        "!=",
                        journal.l10n_pt_doc_provider_id.id or False,
                    ),
                ]
            )
            moves.l10n_pt_doc_provider_id = journal.l10n_pt_doc_provider_id
            for move in moves:
                provider = move._l10n_pt_provider()
                move.l10n_pt_doc_type = (
                    provider.get_document_type(move) if provider is not None else False
                )
        return res
