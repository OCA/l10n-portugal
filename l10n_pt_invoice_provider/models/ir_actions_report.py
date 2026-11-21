# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from io import BytesIO

from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        moves = self.env["account.move"]
        if res_ids and self._is_invoice_report(report_ref):
            moves = moves.browse(res_ids)
        provider_moves = moves.filtered(
            lambda move: move._l10n_pt_requires_provider_pdf()
        )
        if not provider_moves:
            return super()._render_qweb_pdf_prepare_streams(
                report_ref, data, res_ids=res_ids
            )

        streams = {}
        for move in provider_moves:
            attachment = move._l10n_pt_ensure_document_pdf()
            streams[move.id] = {
                "stream": BytesIO(bytes(attachment.raw)),
                "attachment": attachment,
            }
        if native_moves := moves - provider_moves:
            streams.update(
                super()._render_qweb_pdf_prepare_streams(
                    report_ref, data, res_ids=native_moves.ids
                )
            )
        # Restore the requested order and retain any unsplit native PDF.
        ordered = {
            move_id: streams[move_id] for move_id in res_ids if move_id in streams
        }
        ordered.update(streams)
        return ordered
