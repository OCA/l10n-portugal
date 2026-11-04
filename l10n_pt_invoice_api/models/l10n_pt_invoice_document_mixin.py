# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from markupsafe import Markup

from odoo import api, exceptions, fields, models


class L10nPtInvoiceDocumentMixin(models.AbstractModel):
    """Fields and actions for models backed by a legal document provider."""

    _name = "l10n_pt.invoice.document.mixin"
    _description = "Legal Document Mixin"

    l10n_pt_doc_provider = fields.Selection(
        selection="_selection_l10n_pt_doc_provider",
        compute="_compute_l10n_pt_doc_provider",
        store=True,
        readonly=False,
        copy=False,
    )
    l10n_pt_doc_type = fields.Char(
        compute="_compute_l10n_pt_doc_type",
        store=True,
        readonly=False,
        copy=False,
    )
    l10n_pt_doc_id = fields.Char(string="Legal Document ID", copy=False, readonly=True)
    l10n_pt_doc_number = fields.Char(
        string="Legal Document Number", copy=False, readonly=True
    )
    l10n_pt_doc_permalink = fields.Char(
        string="Legal Document Link", copy=False, readonly=True
    )
    l10n_pt_doc_enabled = fields.Boolean(compute="_compute_l10n_pt_doc_enabled")

    @api.model
    def _selection_l10n_pt_doc_provider(self):
        Provider = self.env["l10n_pt.invoice.provider"]
        return [
            (code, Provider._get_provider(code)._description)
            for code in Provider._provider_codes()
        ]

    def _compute_l10n_pt_doc_provider(self):
        # Set the provider code; extending models override this
        self.l10n_pt_doc_provider = False

    def _compute_l10n_pt_doc_type(self):
        for doc in self:
            provider = doc._l10n_pt_provider()
            doc.l10n_pt_doc_type = provider and provider.get_document_type(doc)

    @api.depends("l10n_pt_doc_provider")
    def _compute_l10n_pt_doc_enabled(self):
        # Base floor: a provider is selected. Extending models restrict
        # this further — e.g. account.move requires the journal's
        # provider to also be configured (journal.l10n_pt_doc_enabled).
        for doc in self:
            doc.l10n_pt_doc_enabled = bool(doc.l10n_pt_doc_provider)

    def _l10n_pt_provider(self):
        self.ensure_one()
        Provider = self.env["l10n_pt.invoice.provider"]
        return Provider._get_provider(self.l10n_pt_doc_provider)

    def l10n_pt_create_document(self):
        for doc in self.filtered("l10n_pt_doc_enabled"):
            if not doc.l10n_pt_doc_type:
                raise exceptions.UserError(
                    self.env._(
                        "Document %(doc)s is missing the legal document type!",
                        doc=doc.display_name,
                    )
                )
            provider = doc._l10n_pt_provider()
            provider.create_document(doc)

    def action_l10n_pt_send_email(self, ignore_no_config=False):
        for doc in self.filtered("l10n_pt_doc_enabled"):
            if not doc.l10n_pt_doc_id:
                raise exceptions.UserError(
                    self.env._(
                        "Document %(document)s has no legal document yet.",
                        document=doc.display_name,
                    )
                )
            doc._l10n_pt_provider().email_document(
                doc, ignore_no_config=ignore_no_config
            )

    def action_l10n_pt_view_document(self):
        self.ensure_one()
        if self.l10n_pt_doc_permalink:
            return {
                "type": "ir.actions.act_url",
                "url": self.l10n_pt_doc_permalink,
                "target": "new",
            }

    def _l10n_pt_doc_post_message(self, provider_label):
        doc_link = self.env._(
            "<a class='btn btn-info mr-2' target='new' href=%(link)s>%(name)s</a>",
            link=self.l10n_pt_doc_permalink,
            name=self.env._("View Document"),
        )
        self.message_post(
            body=Markup(
                self.env._(
                    "%(provider)s record has been created for this document:"
                    "<ul><li>Id: %(doc_id)s</li><li>%(doc_link)s</li></ul>",
                    provider=provider_label,
                    doc_id=self.l10n_pt_doc_id,
                    doc_link=doc_link,
                )
            )
        )
