# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64

from odoo import api, fields, models


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ("stock.picking", "l10n_pt.invoice.document.mixin")

    l10n_pt_doc_pdf_id = fields.Many2one(
        "ir.attachment",
        string="Legal Document PDF",
        copy=False,
        readonly=True,
        help="PDF of the transport document retrieved from the provider.",
    )

    @api.depends("picking_type_id.l10n_pt_doc_provider")
    def _compute_l10n_pt_doc_provider(self):
        for picking in self:
            picking.l10n_pt_doc_provider = picking.picking_type_id.l10n_pt_doc_provider

    @api.depends("picking_type_id")
    def _compute_l10n_pt_doc_type(self):
        return super()._compute_l10n_pt_doc_type()

    @api.depends("l10n_pt_doc_provider", "picking_type_id")
    def _compute_l10n_pt_doc_enabled(self):
        Provider = self.env["l10n_pt.invoice.provider"]
        for picking in self:
            provider = Provider._get_provider(picking.l10n_pt_doc_provider)
            picking.l10n_pt_doc_enabled = bool(
                provider is not None and provider.is_available(picking.picking_type_id)
            )

    def _compute_l10n_pt_doc_email_enabled(self):
        for picking in self:
            provider = picking._l10n_pt_provider()
            picking.l10n_pt_doc_email_enabled = bool(
                picking.l10n_pt_doc_enabled
                and provider is not None
                and provider.can_email_document(picking.picking_type_id)
            )

    l10n_pt_doc_email_enabled = fields.Boolean(
        compute="_compute_l10n_pt_doc_email_enabled"
    )

    def button_validate(self):
        res = super().button_validate()
        if res is True:
            for picking in self:
                if picking.l10n_pt_doc_enabled and not picking.l10n_pt_doc_id:
                    picking.l10n_pt_create_document()
                    picking._l10n_pt_sync_document_pdf()
        return res

    def _l10n_pt_sync_document_pdf(self):
        # The provider PDF is stored as an attachment, so the transport
        # document travels with the delivery record.
        for picking in self:
            provider = picking._l10n_pt_provider()
            pdf = provider is not None and provider.get_document_pdf(picking)
            if pdf:
                picking.l10n_pt_doc_pdf_id = self.env["ir.attachment"].create(
                    {
                        "name": (picking.l10n_pt_doc_number or f"{picking.name}-guia")
                        + ".pdf",
                        "datas": base64.b64encode(pdf),
                        "res_model": self._name,
                        "res_id": picking.id,
                    }
                )

    def action_l10n_pt_view_document(self):
        # Fallback to the stored PDF when the provider has no public link
        res = super().action_l10n_pt_view_document()
        if res is None and self.l10n_pt_doc_pdf_id:
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{self.l10n_pt_doc_pdf_id.id}",
                "target": "new",
            }
        return res
