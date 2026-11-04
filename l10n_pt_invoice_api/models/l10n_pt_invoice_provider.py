# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class L10nPtInvoiceProvider(models.AbstractModel):
    """Contract for legal document providers (InvoiceXpress, core AT, ...).

    Provider modules create a model inheriting this contract and set
    ``_provider_code``. Documents use the provider through this API only;
    endpoints and payloads stay in the provider module.
    """

    _name = "l10n_pt.invoice.provider"
    _description = "Legal Document Provider"

    _provider_code = None

    @api.model
    def _provider_codes(self):
        """Return the codes of all registered providers."""
        return [
            code
            for model_name in self.env.registry
            if (code := getattr(self.env[model_name], "_provider_code", None))
        ]

    @api.model
    def _get_provider(self, code):
        """Return the provider model registered for the given code."""
        if not code:
            return
        for model_name in self.env.registry:
            model = self.env[model_name]
            if getattr(model, "_provider_code", None) == code:
                return model

    def is_available(self, company):
        """Return True when the provider is configured for this company."""
        raise NotImplementedError

    def get_document_type(self, document):
        """Return the document type code to use for this document."""
        raise NotImplementedError

    def get_doc_prefix(self, doc_type):
        """Return the legal series prefix for a document type."""
        raise NotImplementedError

    def prepare_document_vals(self, document):
        """Return the provider API payload for this document."""
        raise NotImplementedError

    def create_document(self, document):
        """Create and finalize the legal document on the provider.

        Implementations write ``l10n_pt_doc_id``, ``l10n_pt_doc_permalink``
        and ``l10n_pt_doc_number`` on the document.
        """
        raise NotImplementedError

    def settle_document(self, document):
        """Mark the provider document as paid/settled."""
        raise NotImplementedError

    def get_document_pdf(self, document):
        """Return the legal document's PDF bytes, or None if unavailable."""
        raise NotImplementedError

    def can_email_document(self, company):
        """Return True when the provider supports email sending
        and is configured for it on this company.

        Default False — providers that send email override this.
        """
        return False

    def email_document(self, document, ignore_no_config=False):
        """Send the document by email through the provider."""
        raise NotImplementedError
