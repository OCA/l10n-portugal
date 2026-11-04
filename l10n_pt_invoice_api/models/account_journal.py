# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_pt_doc_provider = fields.Selection(
        selection="_selection_l10n_pt_doc_provider",
        help="Legal document service used for documents on this journal.",
    )
    l10n_pt_doc_enabled = fields.Boolean(
        compute="_compute_l10n_pt_doc_enabled",
        help="Set when the selected provider is configured on the company.",
    )

    @api.model
    def _selection_l10n_pt_doc_provider(self):
        Provider = self.env["l10n_pt.invoice.provider"]
        return [
            (code, Provider._get_provider(code)._description)
            for code in Provider._provider_codes()
        ]

    @api.depends("l10n_pt_doc_provider", "company_id")
    def _compute_l10n_pt_doc_enabled(self):
        Provider = self.env["l10n_pt.invoice.provider"]
        for journal in self:
            provider = Provider._get_provider(journal.l10n_pt_doc_provider)
            journal.l10n_pt_doc_enabled = bool(
                provider and provider.is_available(journal.company_id)
            )
