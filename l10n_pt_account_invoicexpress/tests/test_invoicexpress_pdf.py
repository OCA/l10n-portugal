# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from io import BytesIO
from unittest.mock import Mock, patch

from odoo.exceptions import UserError
from odoo.tests import common
from odoo.tools.pdf import PdfFileWriter

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from .invoicexpress_mock import mock_response

PDF_URL = (
    "https://invoicexpress-documents-pdfs.s3.eu-west-1.amazonaws.com"
    "/documents/277321714.pdf?X-Amz-Signature=fixture"
)


@common.tagged("-at_install", "post_install")
class TestInvoiceXpressPdf(AccountTestInvoicingCommon):
    """The certified PDF comes from api/pdf and is cached on the invoice."""

    def setUp(self):
        super().setUp()
        self.journal = self.company_data["default_journal_sale"]
        self.journal.write(
            {
                "invoicexpress_account_name": "SYNTHETIC",
                "invoicexpress_api_key": "TEST-KEY",
                "invoicexpress_doc_type": "invoice_receipt",
            }
        )
        self.env.company.write({"country_id": self.env.ref("base.pt").id})
        self.provider_record = self.env["l10n_pt.invoice.provider.record"].search(
            [("code", "=", "invoicexpress")], limit=1
        )
        self.assertTrue(self.provider_record)

    def test_print_waits_for_pdf_then_caches_it(self):
        """A pending PDF errors once, then prints and caches the download."""
        pdf = self._make_pdf()
        invoice = self._issued_invoice()
        pending = mock_response({}, status_code=202)
        ready = mock_response({"output": {"pdfUrl": PDF_URL}}, status_code=200)
        download = Mock(status_code=200, content=pdf)
        report = self.env["ir.actions.report"].with_context(force_report_rendering=True)
        with (
            patch("requests.request") as mock_request,
            patch("requests.get", return_value=download) as mock_get,
        ):
            mock_request.side_effect = [pending, ready]
            mock_get.return_value = download
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
            self.assertTrue(invoice.invoice_pdf_report_id)
            # Printing again reuses the cached document: no further HTTP.
            content, _ = report._render_qweb_pdf(
                "account.account_invoices", invoice.ids
            )
            self.assertEqual(content, pdf)
        self.assertEqual(mock_request.call_count, 2)
        for call in mock_request.call_args_list:
            self.assertEqual(call.args[0], "GET")
            self.assertTrue(
                call.args[1].startswith("https://SYNTHETIC.app.invoicexpress.com/"),
                call.args[1],
            )
            self.assertTrue(
                call.args[1].endswith("/api/pdf/277321714.json"), call.args[1]
            )
        mock_get.assert_called_once_with(PDF_URL, timeout=15, allow_redirects=False)

    def test_print_rejects_untrusted_pdf_urls(self):
        """Only allowlisted HTTPS URLs are ever downloaded."""
        for pdf_url in (
            "https://example.test/documents/invoice.pdf",
            "http://invoicexpress-documents-pdfs.s3.eu-west-1.amazonaws.com/documents/invoice.pdf",
            "https://invoicexpress-documents-pdfs.s3.eu-west-1.amazonaws.com.evil.test/documents/invoice.pdf",
            "https://user:pass@invoicexpress-documents-pdfs.s3.eu-west-1.amazonaws.com/documents/invoice.pdf",
        ):
            with self.subTest(pdf_url=pdf_url):
                invoice = self._issued_invoice()
                metadata = mock_response({"output": {"pdfUrl": pdf_url}})
                report = self.env["ir.actions.report"].with_context(
                    force_report_rendering=True
                )
                with (
                    patch("requests.request", return_value=metadata),
                    patch("requests.get") as mock_get,
                ):
                    with self.assertRaisesRegex(
                        UserError, "The legal document PDF is unavailable"
                    ):
                        report._render_qweb_pdf("account.account_invoices", invoice.ids)
                    mock_get.assert_not_called()

    def _issued_invoice(self, doc_id="277321714"):
        """Return a posted invoice marked as issued by InvoiceXpress."""
        invoice = self.init_invoice(
            "out_invoice", amounts=[1000], post=True, journal=self.journal
        )
        invoice.write(
            {
                "l10n_pt_doc_provider_id": self.provider_record.id,
                "l10n_pt_doc_type": "invoice_receipt",
                "l10n_pt_doc_id": doc_id,
            }
        )
        return invoice

    def _make_pdf(self):
        """Return the bytes of a valid one-page blank PDF."""
        buffer = BytesIO()
        writer = PdfFileWriter()
        writer.add_blank_page(200, 200)
        writer.write(buffer)
        return buffer.getvalue()
