# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from contextlib import contextmanager
from io import BytesIO
from unittest.mock import Mock, patch

from odoo.exceptions import UserError
from odoo.tests import common
from odoo.tools import BinaryBytes
from odoo.tools.pdf import PdfFileWriter

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@common.tagged("post_install", "-at_install")
class TestProviderInvoicePdf(AccountTestInvoicingCommon):
    """Provider-backed moves only ever use the provider's official PDF."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider_code = "test_provider"

    def test_direct_print_returns_provider_pdf(self):
        """Print on an issued provider invoice returns the provider PDF."""
        pdf = self._make_pdf()
        with self._issued_invoice(pdf=pdf) as (invoice, stub):
            report = self.env["ir.actions.report"].with_context(
                force_report_rendering=True
            )
            content, report_type = report._render_qweb_pdf(
                "account.account_invoices", invoice.ids
            )
            self.assertEqual(content, pdf)
            self.assertEqual(report_type, "pdf")
            invoice.invalidate_recordset()
            self.assertEqual(bytes(invoice.invoice_pdf_report_id.raw), pdf)
            # Printing again reuses the stored official document.
            content, _ = report._render_qweb_pdf(
                "account.account_invoices", invoice.ids
            )
            self.assertEqual(content, pdf)
        self.assertEqual(stub.get_document_pdf.call_count, 1)

    def test_direct_print_credit_note_returns_provider_pdf(self):
        """Print on an issued provider credit note returns the provider PDF."""
        pdf = self._make_pdf()
        with self._issued_invoice(pdf=pdf, move_type="out_refund") as (
            invoice,
            stub,
        ):
            content, report_type = (
                self.env["ir.actions.report"]
                .with_context(force_report_rendering=True)
                ._render_qweb_pdf("account.account_invoices", invoice.ids)
            )
            self.assertEqual(content, pdf)
            self.assertEqual(report_type, "pdf")
        stub.get_document_pdf.assert_called_once()

    def test_send_blocked_when_provider_pdf_unavailable(self):
        """Send & Print reports a retryable error instead of any PDF."""
        with self._issued_invoice(pdf=None) as (invoice, stub):
            message_count = len(invoice.message_ids)
            attachments = self.env["account.move.send"]._generate_and_send_invoices(
                invoice, allow_fallback_pdf=True
            )
            invoice.invalidate_recordset()
            self.assertFalse(attachments)
            self.assertFalse(invoice.invoice_pdf_report_id)
            self.assertFalse(invoice.invoice_pdf_report_file)
            self.assertFalse(invoice.message_main_attachment_id)
            self.assertGreater(len(invoice.message_ids), message_count)
            stub.get_document_pdf.assert_called()

    def test_send_raises_when_provider_pdf_unavailable_without_fallback(self):
        """Without fallback, the same situation surfaces as a UserError."""
        with (
            self._issued_invoice(pdf=None) as (invoice, _stub),
            self.assertRaises(UserError),
        ):
            self.env["account.move.send"]._generate_and_send_invoices(
                invoice, allow_fallback_pdf=False
            )

    def test_print_blocked_without_remote_document_id(self):
        """A provider move that was never issued cannot be printed."""
        with self._issued_invoice(pdf=self._make_pdf(), doc_id=None) as (
            invoice,
            stub,
        ):
            with self.assertRaises(UserError):
                self.env["ir.actions.report"].with_context(
                    force_report_rendering=True
                )._render_qweb_pdf("account.account_invoices", invoice.ids)
            self.assertFalse(invoice.invoice_pdf_report_id)
        stub.get_document_pdf.assert_not_called()
        stub.create_document.assert_not_called()

    def test_send_uses_provider_pdf_not_local(self):
        """Send & Print sends the provider PDF, never a local copy."""
        pdf = self._make_pdf()
        local_pdf = b"locally rendered pdf"
        with self._issued_invoice(pdf=pdf) as (invoice, stub):
            invoice.invoice_pdf_report_file = BinaryBytes(local_pdf)
            invoice.invalidate_recordset()
            self.assertEqual(bytes(invoice.invoice_pdf_report_id.raw), local_pdf)
            attachments = self.env["account.move.send"]._generate_and_send_invoices(
                invoice, allow_fallback_pdf=True
            )
            invoice.invalidate_recordset()
            self.assertTrue(attachments)
            self.assertEqual(bytes(invoice.invoice_pdf_report_id.raw), pdf)
            self.assertTrue(any(bytes(a.raw) == pdf for a in attachments))
            self.assertFalse(any(bytes(a.raw) == local_pdf for a in attachments))
            stub.get_document_pdf.assert_called()

    def test_post_keeps_issuance_when_provider_pdf_unavailable(self):
        """Issuance succeeds even when the provider has no PDF yet."""
        stub = self._provider_stub(None)

        def _create_document(move):
            move.write(
                {
                    "l10n_pt_doc_id": "remote-id",
                    "l10n_pt_doc_number": "FT A/1",
                }
            )

        stub.create_document.side_effect = _create_document
        with self._provider_patch(stub) as record:
            journal = self.company_data["default_journal_sale"]
            journal.write({"l10n_pt_doc_provider_id": record.id})
            invoice = self.init_invoice(
                "out_invoice", amounts=[1000], post=False, journal=journal
            )
            invoice.action_post()
            invoice.invalidate_recordset()
            self.assertEqual(invoice.state, "posted")
            self.assertEqual(invoice.l10n_pt_doc_id, "remote-id")
            self.assertFalse(invoice.invoice_pdf_report_id)
            self.assertFalse(invoice.invoice_pdf_report_file)
        stub.create_document.assert_called_once()
        stub.get_document_pdf.assert_called()

    def test_pt_invoice_without_provider_uses_proforma_title(self):
        """A posted PT customer invoice with no provider renders proforma."""
        invoice = self.init_invoice("out_invoice", amounts=[1000], post=True)
        pt = self.env.ref("base.pt")
        invoice.company_id.write(
            {"country_id": pt.id, "account_fiscal_country_id": pt.id}
        )
        invoice.invalidate_recordset()
        self.assertEqual(invoice.country_code, "PT")
        self.assertFalse(invoice.l10n_pt_doc_provider_id)
        self.assertFalse(invoice.l10n_pt_doc_id)
        html = self.env["ir.actions.report"]._render_qweb_html(
            "account.account_invoices", invoice.ids
        )[0]
        self.assertIn(b"Proforma Invoice", html)

    def test_native_title_kept_for_non_qualifying_invoices(self):
        """Non-PT, draft, credit note and provider moves are not proforma."""
        report = self.env["ir.actions.report"]
        invoice = self.init_invoice("out_invoice", amounts=[1000], post=True)
        html = report._render_qweb_html("account.account_invoices", invoice.ids)[0]
        self.assertNotIn(b"Proforma Invoice", html)

        pt = self.env.ref("base.pt")
        invoice.company_id.write(
            {"country_id": pt.id, "account_fiscal_country_id": pt.id}
        )

        draft = self.init_invoice("out_invoice", amounts=[1000], post=False)
        html = report._render_qweb_html("account.account_invoices", draft.ids)[0]
        self.assertNotIn(b"Proforma Invoice", html)

        refund = self.init_invoice("out_refund", amounts=[1000], post=True)
        html = report._render_qweb_html("account.account_invoices", refund.ids)[0]
        self.assertNotIn(b"Proforma Invoice", html)

        pdf = self._make_pdf()
        with self._issued_invoice(pdf=pdf) as (provider_invoice, _stub):
            html = report._render_qweb_html(
                "account.account_invoices", provider_invoice.ids
            )[0]
            self.assertNotIn(b"Proforma Invoice", html)

    def test_journal_provider_change_keeps_posted_document(self):
        """Journal edits refresh unissued drafts; issued docs keep their values."""
        pdf = self._make_pdf()
        journal = self.company_data["default_journal_sale"]
        stub = self._provider_stub(pdf)

        def _create_document(move):
            move.write(
                {
                    "l10n_pt_doc_id": "remote-id",
                    "l10n_pt_doc_number": "FT A/1",
                }
            )

        stub.create_document.side_effect = _create_document
        with self._provider_patch(stub) as record:
            old_draft = self.init_invoice(
                "out_invoice", amounts=[1000], post=False, journal=journal
            )
            posted_plain = self.init_invoice(
                "out_invoice", amounts=[1000], post=True, journal=journal
            )
            self.assertFalse(old_draft.l10n_pt_doc_provider_id)
            self.assertFalse(old_draft.l10n_pt_doc_type)
            self.assertFalse(posted_plain.l10n_pt_doc_provider_id)
            journal.write({"l10n_pt_doc_provider_id": record.id})
            self.assertEqual(old_draft.l10n_pt_doc_provider_id, record)
            self.assertEqual(old_draft.l10n_pt_doc_type, "invoice")
            self.assertFalse(posted_plain.l10n_pt_doc_provider_id)
            new_draft = self.init_invoice(
                "out_invoice", amounts=[1000], post=False, journal=journal
            )
            self.assertEqual(new_draft.l10n_pt_doc_provider_id, record)
            self.assertEqual(new_draft.l10n_pt_doc_type, "invoice")
            new_draft.action_post()
            self.assertEqual(new_draft.l10n_pt_doc_provider_id, record)
            self.assertEqual(new_draft.l10n_pt_doc_type, "invoice")
            journal.write({"l10n_pt_doc_provider_id": False})
            old_draft.invalidate_recordset()
            new_draft.invalidate_recordset()
            posted_plain.invalidate_recordset()
            self.assertFalse(old_draft.l10n_pt_doc_provider_id)
            self.assertFalse(old_draft.l10n_pt_doc_type)
            self.assertFalse(posted_plain.l10n_pt_doc_provider_id)
            self.assertEqual(new_draft.l10n_pt_doc_provider_id, record)
            self.assertEqual(new_draft.l10n_pt_doc_type, "invoice")
            content, _ = (
                self.env["ir.actions.report"]
                .with_context(force_report_rendering=True)
                ._render_qweb_pdf("account.account_invoices", new_draft.ids)
            )
            self.assertEqual(content, pdf)
        stub.get_document_pdf.assert_called_once()

    def test_post_blocked_when_provider_differs_from_journal(self):
        """Posting requires the stored provider to match the journal's."""
        journal = self.company_data["default_journal_sale"]
        stub = self._provider_stub(self._make_pdf())

        def _create_document(move):
            move.write(
                {
                    "l10n_pt_doc_id": "remote-id",
                    "l10n_pt_doc_number": "FT A/1",
                }
            )

        stub.create_document.side_effect = _create_document
        expected = (
            r"The legal document provider on .+ does not match "
            r"the provider configured on journal .+\."
        )
        with self._provider_patch(stub) as record:
            # Stored provider set while the journal has none.
            invoice = self.init_invoice(
                "out_invoice", amounts=[1000], post=False, journal=journal
            )
            invoice.l10n_pt_doc_provider_id = record
            with (
                self.assertRaisesRegex(UserError, expected),
                self.env.cr.savepoint(),
            ):
                invoice.action_post()
            invoice.invalidate_recordset()
            self.assertEqual(invoice.state, "draft")
            stub.create_document.assert_not_called()

            # Journal provider set, then the draft's provider cleared.
            journal.write({"l10n_pt_doc_provider_id": record.id})
            cleared = self.init_invoice(
                "out_invoice", amounts=[1000], post=False, journal=journal
            )
            self.assertEqual(cleared.l10n_pt_doc_provider_id, record)
            cleared.l10n_pt_doc_provider_id = False
            with (
                self.assertRaisesRegex(UserError, expected),
                self.env.cr.savepoint(),
            ):
                cleared.action_post()
            cleared.invalidate_recordset()
            self.assertEqual(cleared.state, "draft")
        stub.create_document.assert_not_called()

    def test_uninstalled_adapter_keeps_cached_pdf(self):
        """Issued documents keep cached PDFs after the adapter is removed."""
        pdf = self._make_pdf()
        stub = self._provider_stub(pdf)
        with self._provider_patch(stub) as record:
            cached_invoice = self.init_invoice("out_invoice", amounts=[1000], post=True)
            cached_invoice.write(
                {
                    "l10n_pt_doc_provider_id": record.id,
                    "l10n_pt_doc_id": "remote-id",
                }
            )
            uncached_invoice = self.init_invoice(
                "out_invoice", amounts=[1000], post=True
            )
            uncached_invoice.write(
                {
                    "l10n_pt_doc_provider_id": record.id,
                    "l10n_pt_doc_id": "remote-id-2",
                }
            )
            content, _ = (
                self.env["ir.actions.report"]
                .with_context(force_report_rendering=True)
                ._render_qweb_pdf("account.account_invoices", cached_invoice.ids)
            )
            self.assertEqual(content, pdf)
        # The adapter implementation is gone; the registration row remains.
        for invoice in (cached_invoice, uncached_invoice):
            invoice.invalidate_recordset()
        record.invalidate_recordset()
        self.assertTrue(record.exists())
        self.assertEqual(cached_invoice.l10n_pt_doc_provider_id, record)
        records = self.env["l10n_pt.invoice.provider.record"]
        self.assertNotIn(record, records.search([("adapter_installed", "=", True)]))
        self.assertIn(record, records.search([("adapter_installed", "=", False)]))
        # The cached PDF still prints without the adapter.
        content, _ = (
            self.env["ir.actions.report"]
            .with_context(force_report_rendering=True)
            ._render_qweb_pdf("account.account_invoices", cached_invoice.ids)
        )
        self.assertEqual(content, pdf)
        # Without a cached PDF, printing reports the missing adapter.
        with self.assertRaisesRegex(UserError, "is not installed"):
            self.env["ir.actions.report"].with_context(
                force_report_rendering=True
            )._render_qweb_pdf("account.account_invoices", uncached_invoice.ids)
        # Re-registering resolves to the same durable record.
        with self._provider_patch(stub):
            self.assertEqual(
                self.env["l10n_pt.invoice.provider.record"]
                ._register_provider(self.provider_code)
                .id,
                record.id,
            )

    def test_legal_documents_use_provider_pdf(self):
        """Portal and direct download return the provider PDF, not a stale copy."""
        pdf = self._make_pdf()
        with self._issued_invoice(pdf=pdf) as (invoice, stub):
            invoice.invoice_pdf_report_file = BinaryBytes(b"locally rendered pdf")
            invoice.invalidate_recordset()
            documents = invoice._get_invoice_legal_documents_all(allow_fallback=True)
            self.assertEqual(
                [bytes(document["content"]) for document in documents], [pdf]
            )
            document = invoice._get_invoice_legal_documents("pdf", allow_fallback=True)
            self.assertEqual(len(document), 1)
            self.assertEqual(bytes(document[0]["content"]), pdf)
        stub.get_document_pdf.assert_called_once()

    def test_legal_documents_error_when_provider_pdf_unavailable(self):
        """Download paths surface the retryable error instead of a stale PDF."""
        with self._issued_invoice(pdf=None) as (invoice, stub):
            invoice.invoice_pdf_report_file = BinaryBytes(b"locally rendered pdf")
            invoice.invalidate_recordset()
            for call in (
                lambda: invoice._get_invoice_legal_documents_all(allow_fallback=True),
                lambda: invoice._get_invoice_legal_documents(
                    "pdf", allow_fallback=True
                ),
            ):
                with self.assertRaises(UserError) as error:
                    call()
                self.assertIn(
                    "The legal document PDF is unavailable", str(error.exception)
                )
        stub.get_document_pdf.assert_called()

    def _make_pdf(self):
        """Return the bytes of a valid one-page blank PDF."""
        buffer = BytesIO()
        writer = PdfFileWriter()
        writer.add_blank_page(200, 200)
        writer.write(buffer)
        return buffer.getvalue()

    def _provider_stub(self, pdf):
        """Return a stub implementing the provider contract under test."""
        stub = Mock()
        stub._description = "Test Provider"
        stub.is_available.return_value = True
        stub.get_document_type.return_value = "invoice"
        stub.get_document_pdf.return_value = pdf
        stub.get_doc_prefix.return_value = "FT"
        stub.can_email_document.return_value = False
        return stub

    @contextmanager
    def _provider_patch(self, stub):
        """Resolve ``test_provider`` to ``stub`` and yield its record."""
        provider_cls = type(self.env["l10n_pt.invoice.provider"])
        with (
            patch.object(
                provider_cls,
                "_get_provider",
                side_effect=lambda code: stub if code == self.provider_code else None,
            ),
            patch.object(
                provider_cls, "_provider_codes", return_value=[self.provider_code]
            ),
        ):
            record = self.env["l10n_pt.invoice.provider.record"]._register_provider(
                self.provider_code
            )
            yield record

    @contextmanager
    def _issued_invoice(self, pdf=None, doc_id="remote-id", move_type="out_invoice"):
        """Yield ``(invoice, stub)`` for a posted move on the stub provider."""
        invoice = self.init_invoice(move_type, amounts=[1000], post=True)
        stub = self._provider_stub(pdf)
        with self._provider_patch(stub) as record:
            vals = {"l10n_pt_doc_provider_id": record.id}
            if doc_id is not None:
                vals["l10n_pt_doc_id"] = doc_id
            invoice.write(vals)
            yield invoice, stub
