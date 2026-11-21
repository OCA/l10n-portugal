# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from io import BytesIO
from unittest.mock import Mock, patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import Form, common
from odoo.tools.pdf import PdfFileWriter

from .invoicexpress_mock import mock_request_side_effect, mock_response

PDF_URL = (
    "https://invoicexpress-documents-pdfs.s3.eu-west-1.amazonaws.com"
    "/documents/12345678.pdf?X-Amz-Signature=fixture"
)


@common.tagged("-at_install", "post_install")
class TestInvoiceXpressPdf(common.TransactionCase):
    """Issued invoices print the certified InvoiceXpress PDF, fetched on demand."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.write(
            {
                "invoicexpress_account_name": "ACCOUNT",
                "invoicexpress_api_key": "APIKEY",
                "country_id": self.env.ref("base.pt").id,
            }
        )
        self.sale_journals = self.env["account.journal"].search([("type", "=", "sale")])
        self.sale_journals.write({"invoicexpress_doc_type": "invoice_receipt"})
        self.partner = self.env["res.partner"].create(
            {
                "name": "Customer A",
                "country_id": self.env.ref("base.pt").id,
                "city": "Porto",
                "zip": "2000-555",
            }
        )
        self.product = self.env["product.product"].create(
            {"name": "Product A", "list_price": "2.0"}
        )

    def test_print_waits_for_pdf_then_caches_it(self):
        """A pending PDF errors once, then prints and caches the download."""
        pdf = self._make_pdf()
        with (
            patch("requests.request") as mock_request,
            patch("requests.get") as mock_get,
        ):
            invoice = self._issue_invoice(mock_request)
            stale_pdf = self._add_stale_pdf(invoice)
            self.assertFalse(stale_pdf.invoicexpress_certified_pdf)
            mock_request.reset_mock()
            pending = mock_response({}, status_code=202)
            ready = mock_response({"output": {"pdfUrl": PDF_URL}})
            mock_request.side_effect = [pending, ready]
            mock_get.return_value = Mock(status_code=200, content=pdf)
            report = self.env["ir.actions.report"].with_context(
                force_report_rendering=True
            )
            # The provider is still generating the document.
            with self.assertRaises(UserError):
                report._render_qweb_pdf("account.account_invoices", invoice.ids)
            mock_get.assert_not_called()
            # Once ready, the signed URL is downloaded and becomes the
            # invoice's reference document.
            content, report_type = report._render_qweb_pdf(
                "account.account_invoices", invoice.ids
            )
            self.assertEqual(content, pdf)
            self.assertEqual(report_type, "pdf")
            invoice.invalidate_recordset()
            certified_pdf = invoice.invoice_pdf_report_id
            self.assertTrue(certified_pdf.invoicexpress_certified_pdf)
            self.assertEqual(bytes(certified_pdf.raw), pdf)
            stale_pdf.invalidate_recordset()
            self.assertFalse(stale_pdf.res_field)
            # Printing again reuses the cached document: no further HTTP.
            content, _ = report._render_qweb_pdf(
                "account.account_invoices", invoice.ids
            )
            self.assertEqual(content, pdf)
        self.assertEqual(mock_request.call_count, 2)
        for call in mock_request.call_args_list:
            self.assertEqual(call.args[0], "GET")
            self.assertTrue(
                call.args[1].startswith("https://ACCOUNT.app.invoicexpress.com/"),
                call.args[1],
            )
            self.assertTrue(
                call.args[1].endswith("/api/pdf/12345678.json"), call.args[1]
            )
        mock_get.assert_called_once_with(PDF_URL, timeout=15, allow_redirects=False)

    def test_send_uses_certified_pdf_not_stale_copy(self):
        """Send & Print sends the certified PDF, never a local substitute."""
        pdf = self._make_pdf()
        with (
            patch("requests.request") as mock_request,
            patch("requests.get") as mock_get,
        ):
            invoice = self._issue_invoice(mock_request)
            self._add_stale_pdf(invoice)
            mock_request.reset_mock()
            ready = mock_response({"output": {"pdfUrl": PDF_URL}})
            mock_request.side_effect = [ready]
            mock_get.return_value = Mock(status_code=200, content=pdf)
            attachments = self.env["account.move.send"]._generate_and_send_invoices(
                invoice, sending_methods={"manual"}, allow_fallback_pdf=True
            )
            invoice.invalidate_recordset()
            self.assertTrue(attachments)
            self.assertEqual(attachments, invoice.invoice_pdf_report_id)
            self.assertTrue(invoice.invoice_pdf_report_id.invoicexpress_certified_pdf)
            self.assertEqual(bytes(invoice.invoice_pdf_report_id.raw), pdf)
            self.assertFalse(
                any(
                    not attachment.invoicexpress_certified_pdf
                    for attachment in attachments
                )
            )
        mock_get.assert_called_once_with(PDF_URL, timeout=15, allow_redirects=False)

    def test_send_reports_retryable_error_when_pdf_pending(self):
        """Send & Print reports a retryable error instead of any substitute."""
        with (
            patch("requests.request") as mock_request,
            patch("requests.get") as mock_get,
        ):
            invoice = self._issue_invoice(mock_request)
            self._add_stale_pdf(invoice)
            message_count = len(invoice.message_ids)
            mock_request.reset_mock()
            pending = mock_response({}, status_code=202)
            mock_request.side_effect = [pending]
            attachments = self.env["account.move.send"]._generate_and_send_invoices(
                invoice, sending_methods={"manual"}, allow_fallback_pdf=True
            )
            invoice.invalidate_recordset()
            self.assertFalse(attachments)
            self.assertFalse(invoice.invoice_pdf_report_id.invoicexpress_certified_pdf)
            self.assertGreater(len(invoice.message_ids), message_count)
            mock_get.assert_not_called()

    def test_legal_documents_return_certified_pdf(self):
        """Portal and direct download return the certified PDF only."""
        pdf = self._make_pdf()
        with (
            patch("requests.request") as mock_request,
            patch("requests.get") as mock_get,
        ):
            invoice = self._issue_invoice(mock_request)
            self._add_stale_pdf(invoice)
            mock_request.reset_mock()
            ready = mock_response({"output": {"pdfUrl": PDF_URL}})
            mock_request.side_effect = [ready]
            mock_get.return_value = Mock(status_code=200, content=pdf)
            documents = invoice._get_invoice_legal_documents_all(allow_fallback=True)
            self.assertEqual(len(documents), 1)
            self.assertEqual(bytes(documents[0]["content"]), pdf)
            document = invoice._get_invoice_legal_documents("pdf", allow_fallback=True)
            self.assertEqual(bytes(document["content"]), pdf)
        # Both calls reuse the cached document: a single metadata request.
        self.assertEqual(mock_request.call_count, 1)
        mock_get.assert_called_once_with(PDF_URL, timeout=15, allow_redirects=False)

    def test_legal_documents_error_when_pdf_pending(self):
        """Download paths surface the retryable error instead of a stale PDF."""
        with (
            patch("requests.request") as mock_request,
            patch("requests.get") as mock_get,
        ):
            invoice = self._issue_invoice(mock_request)
            self._add_stale_pdf(invoice)
            mock_request.reset_mock()
            mock_request.side_effect = [mock_response({}, status_code=202)] * 2
            for call in (
                lambda: invoice._get_invoice_legal_documents_all(allow_fallback=True),
                lambda: invoice._get_invoice_legal_documents(
                    "pdf", allow_fallback=True
                ),
            ):
                with self.assertRaisesRegex(
                    UserError, "The InvoiceXpress PDF is unavailable"
                ):
                    call()
            mock_get.assert_not_called()

    def test_print_rejects_untrusted_pdf_urls(self):
        """Only allowlisted HTTPS URLs are ever downloaded."""
        with (
            patch("requests.request") as mock_request,
            patch("requests.get") as mock_get,
        ):
            invoice = self._issue_invoice(mock_request)
            mock_request.reset_mock()
            report = self.env["ir.actions.report"].with_context(
                force_report_rendering=True
            )
            for pdf_url in (
                "https://example.test/documents/invoice.pdf",
                "http://invoicexpress-documents-pdfs.s3.eu-west-1.amazonaws.com/documents/invoice.pdf",
                "https://invoicexpress-documents-pdfs.s3.eu-west-1.amazonaws.com.evil.test/documents/invoice.pdf",
                "https://user:pass@invoicexpress-documents-pdfs.s3.eu-west-1.amazonaws.com/documents/invoice.pdf",
            ):
                with self.subTest(pdf_url=pdf_url):
                    metadata = mock_response({"output": {"pdfUrl": pdf_url}})
                    mock_request.side_effect = [metadata]
                    with self.assertRaisesRegex(
                        UserError, "The InvoiceXpress PDF is unavailable"
                    ):
                        report._render_qweb_pdf("account.account_invoices", invoice.ids)
            mock_get.assert_not_called()

    def test_print_mixed_native_and_certified_invoices(self):
        """A batch print keeps request order: native render plus certified."""
        pdf = self._make_pdf()
        native_pdf = self._make_pdf(width=300)
        with (
            patch("requests.request") as mock_request,
            patch("requests.get") as mock_get,
        ):
            # Post a plain invoice while InvoiceXpress is disabled.
            self.sale_journals.write({"invoicexpress_doc_type": "none"})
            native = self._issue_plain_invoice()
            self.assertFalse(native.invoicexpress_id)
            self.sale_journals.write({"invoicexpress_doc_type": "invoice_receipt"})
            certified = self._issue_invoice(mock_request)
            mock_request.reset_mock()
            ready = mock_response({"output": {"pdfUrl": PDF_URL}})
            mock_request.side_effect = [ready]
            mock_get.return_value = Mock(status_code=200, content=pdf)
            report = self.env["ir.actions.report"].with_context(
                force_report_rendering=True
            )
            with patch.object(
                type(report),
                "_run_wkhtmltopdf",
                return_value=native_pdf,
            ) as render_pdf:
                streams, report_type = report._pre_render_qweb_pdf(
                    "account.account_invoices", [native.id, certified.id]
                )
            render_pdf.assert_called_once()
            self.assertEqual(report_type, "pdf")
            self.assertEqual(list(streams), [native.id, certified.id])
            self.assertTrue(
                streams[certified.id]["attachment"].invoicexpress_certified_pdf
            )
            self.assertEqual(streams[certified.id]["stream"].getvalue(), pdf)
            self.assertEqual(streams[native.id]["stream"].getvalue(), native_pdf)
        mock_get.assert_called_once_with(PDF_URL, timeout=15, allow_redirects=False)

    def _issue_invoice(self, mock_request):
        """Post an invoice issued through the mocked InvoiceXpress API."""
        mock_request.side_effect = mock_request_side_effect
        move_form = Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        )
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partner
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product
        invoice = move_form.save()
        invoice.action_post()
        self.assertTrue(invoice.invoicexpress_id)
        return invoice

    def _add_stale_pdf(self, invoice):
        """Attach a locally rendered PDF the way Odoo stores report files."""
        return self.env["ir.attachment"].create(
            {
                "name": "invoice.pdf",
                "res_model": "account.move",
                "res_id": invoice.id,
                "res_field": "invoice_pdf_report_file",
                "mimetype": "application/pdf",
                "raw": b"locally rendered pdf",
            }
        )

    def _issue_plain_invoice(self):
        """Post an invoice while InvoiceXpress is disabled on its journal."""
        move_form = Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        )
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partner
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product
        invoice = move_form.save()
        invoice.action_post()
        return invoice

    def _make_pdf(self, width=200):
        """Return the bytes of a valid one-page blank PDF."""
        buffer = BytesIO()
        writer = PdfFileWriter()
        writer.addBlankPage(width, 200)
        writer.write(buffer)
        return buffer.getvalue()
