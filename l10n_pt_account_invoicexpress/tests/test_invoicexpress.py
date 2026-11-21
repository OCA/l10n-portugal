import json
import os
from unittest.mock import patch

import requests

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import Form, common
from odoo.tools import mute_logger

from .invoicexpress_mock import mock_request_side_effect, mock_response


@common.tagged("-at_install", "post_install")
class TestInvoiceXpress(common.TransactionCase):
    def setUp(self):
        super().setUp()

        self.company = self.env.company
        self.company.write({"country_id": self.env.ref("base.pt").id})
        Journal = self.env["account.journal"]
        self.sale_journals = Journal.search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)]
        )
        self.sale_journals.write(
            {
                "invoicexpress_account_name": "ACCOUNT",
                "invoicexpress_api_key": "APIKEY",
            }
        )

        self.AccountMove = self.env["account.move"]
        self.ProductProduct = self.env["product.product"]
        self.ResPartner = self.env["res.partner"]
        self.AccountTax = self.env["account.tax"]

        self.productA = self.ProductProduct.create(
            {"name": "Product A", "list_price": "2.0"}
        )
        self.productB = self.ProductProduct.create(
            {"name": "Product B", "list_price": "3.0"}
        )

        self.pt_country = self.env.ref("base.pt")
        self.partnerA = self.ResPartner.create(
            {
                "name": "Customer A",
                "country_id": self.pt_country.id,
                "city": "Porto",
                "zip": "2000-555",
            }
        )

    def test_res_partner__prepare_invoicexpress_vals(self):
        partner_PT = self.partnerA.copy({"country_id": self.env.ref("base.pt").id})
        partner_PT_vals = partner_PT._prepare_invoicexpress_vals()
        self.assertEqual(
            partner_PT_vals["language"], "pt", "Address in Portugal uses pt language"
        )
        partner_ES = self.partnerA.copy({"country_id": self.env.ref("base.es").id})
        partner_ES_vals = partner_ES._prepare_invoicexpress_vals()
        self.assertEqual(
            partner_ES_vals["language"], "es", "Address in Spain uses es language"
        )
        partner_FR = self.partnerA.copy({"country_id": self.env.ref("base.fr").id})
        partner_FR_vals = partner_FR._prepare_invoicexpress_vals()
        self.assertEqual(
            partner_FR_vals["language"],
            "en",
            "Address not in Spain or Portugal uses en language",
        )

    def test_010_get_config_and_base_url(self):
        API = self.env["account.provider.invoicexpress"]
        url = API._build_url(API._get_config(self.sale_journals[0]), "dummy.json")
        self.assertEqual(url, "https://ACCOUNT.app.invoicexpress.com/dummy.json")

    @patch.object(requests, "request")
    def test_100_create_invoicexpress_tax(self, mock_request):
        mock_request.return_value = mock_response(
            {
                "tax": {
                    "id": 12345,
                    "name": "IVA23",
                    "value": 23.0,
                    "region": "PT",
                    "default_tax": 1,
                }
            }
        )
        taxA = self.env["account.tax"].create(
            {
                "name": "IVA23",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": 23.0,
            }
        )
        taxA.action_invoicexpress_tax_create(journal=self.sale_journals[0])
        self.assertEqual(taxA.invoicexpress_id, "12345")

    @patch("requests.request")
    def test_101_create_invoicexpress_invoice(self, mock_request):
        mock_request.side_effect = mock_request_side_effect
        tax = self._make_invoice_tax("IVA23", 23)
        invoice = self._make_invoice_with_taxes(tax, tax)
        invoice.journal_id.write(
            {
                "invoicexpress_account_name": "SALES",
                "invoicexpress_api_key": "SALES-KEY",
            }
        )
        invoice.action_post()
        self.assertEqual(invoice.l10n_pt_doc_type, "invoice_receipt")
        self.assertEqual(invoice.l10n_pt_doc_id, "12345678")
        self.assertEqual(invoice.name, "FR MYSEQ/123")
        self.assertNotIn("tax_exemption", self._get_sent_invoice(mock_request))
        self.assertTrue(mock_request.call_args_list)
        for call in mock_request.call_args_list:
            self.assertTrue(
                call.args[1].startswith("https://SALES.app.invoicexpress.com/"),
                call.args[1],
            )
            self.assertEqual(call.kwargs["params"]["api_key"], "SALES-KEY")

    @patch("requests.request")
    def test_invoice_email_via_provider_requires_journal_opt_in(self, mock_request):
        """Only journals with a template offer explicit InvoiceXpress delivery."""
        mock_request.side_effect = mock_request_side_effect
        self.partnerA.email = "customer@example.test"
        tax = self._make_invoice_tax("IVA23", 23)
        invoice = self._make_invoice_with_taxes(tax)
        invoice.action_post()
        self.assertFalse(invoice.l10n_pt_doc_email_enabled)
        self.assertFalse(
            any(
                "email-document.json" in call.args[1]
                for call in mock_request.call_args_list
            )
        )
        mock_request.reset_mock()
        with self.assertRaisesRegex(
            UserError, "Configure the InvoiceXpress email template"
        ):
            invoice.action_l10n_pt_send_email()
        mock_request.assert_not_called()

        invoice.journal_id.invoicexpress_template_id = self.env.ref(
            "l10n_pt_account_invoicexpress.email_template_invoice"
        )
        self.assertTrue(invoice.l10n_pt_doc_email_enabled)
        invoice.action_l10n_pt_send_email()
        mock_request.assert_called_once()
        call = mock_request.call_args
        self.assertEqual(call.args[0], "PUT")
        self.assertTrue(
            call.args[1].endswith("/invoice_receipts/12345678/email-document.json")
        )
        self.assertEqual(
            json.loads(call.kwargs["data"])["message"]["client"]["email"],
            "customer@example.test",
        )
        invoice.journal_id.invoicexpress_template_id = False
        self.assertFalse(invoice.l10n_pt_doc_email_enabled)

    @patch("requests.request")
    def test_same_exemption_sent_at_document_level(self, mock_request):
        mock_request.side_effect = mock_request_side_effect
        tax_a = self._make_invoice_tax("Exempt A", 0, reason="M07")
        tax_b = self._make_invoice_tax("Exempt B", 0, reason="M07")
        taxable = self._make_invoice_tax("IVA23", 23)
        invoice = self._make_invoice_with_taxes(tax_a, tax_b, taxable)
        self.assertEqual(invoice.invoicexpress_tax_exemption, "M07")
        invoice.action_post()
        payload = self._get_sent_invoice(mock_request)
        self.assertEqual(payload["tax_exemption"], "M07")
        self.assertEqual(len(payload["items"]), 3)

    @patch("requests.request")
    def test_mixed_exemptions_block_before_provider_request(self, mock_request):
        mock_request.side_effect = mock_request_side_effect
        tax_a = self._make_invoice_tax("Exempt A", 0, reason="M07")
        tax_b = self._make_invoice_tax("Exempt B", 0, reason="M16")
        taxable = self._make_invoice_tax("IVA23", 23)
        invoice = self._make_invoice_with_taxes(tax_a, tax_b, taxable)
        with self.assertRaisesRegex(UserError, "M07, M16"):
            invoice.action_post()
        mock_request.assert_not_called()

    @patch("requests.request")
    def test_invoice_rejects_negative_lines_before_http(self, mock_request):
        mock_request.side_effect = mock_request_side_effect
        tax = self._make_invoice_tax("IVA23", 23)
        invoice = self._make_invoice_with_taxes(tax, tax)
        lines = invoice.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        lines[0].price_unit = 10
        second_line = lines[1]
        for negative in (
            {"price_unit": -1, "quantity": 1},
            {"price_unit": 1, "quantity": -1},
        ):
            with self.subTest(negative=negative):
                second_line.write(negative)
                self.assertGreater(invoice.amount_total, 0)
                with (
                    self.assertRaisesRegex(
                        UserError,
                        "InvoiceXpress does not accept a negative unit price "
                        "or quantity",
                    ),
                    self.env.cr.savepoint(),
                ):
                    invoice.action_post()
                self.assertEqual(invoice.state, "draft")
        mock_request.assert_not_called()

    def _make_invoice_with_taxes(self, *taxes):
        provider = self.env["l10n_pt.invoice.provider.record"].search(
            [("code", "=", "invoicexpress")], limit=1
        )
        self.assertTrue(provider)
        self.sale_journals.write(
            {
                "l10n_pt_doc_provider_id": provider.id,
                "invoicexpress_doc_type": "invoice_receipt",
            }
        )
        move_form = Form(self.AccountMove.with_context(default_move_type="out_invoice"))
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partnerA
        for tax in taxes:
            with move_form.invoice_line_ids.new() as line:
                line.product_id = self.productA
                line.tax_ids.clear()
                line.tax_ids.add(tax)
        return move_form.save()

    def _make_invoice_tax(self, name, amount, reason=False):
        return self.AccountTax.create(
            {
                "name": name,
                "type_tax_use": "sale",
                "amount": amount,
                "amount_type": "percent",
                "l10n_pt_tax_exemption_reason": reason,
            }
        )

    def _get_sent_invoice(self, mock_request):
        return next(
            json.loads(call.kwargs["data"])["invoice"]
            for call in mock_request.call_args_list
            if call.args[0] == "POST"
            and call.args[1].endswith("/invoice_receipts.json")
        )


@common.tagged("-standard", "-at_install", "post_install", "invoicexpress_live")
class TestInvoiceXpressLive(common.TransactionCase):
    @mute_logger(
        "odoo.addons.l10n_pt_account_invoicexpress.models.account_invoicexpress",
        "urllib3.connectionpool",
    )
    def test_list_taxes(self):
        """A configured journal can authenticate and read the remote tax list."""
        account_name = os.environ.get("INVOICEXPRESS_ACCOUNT_NAME")
        api_key = os.environ.get("INVOICEXPRESS_API_KEY")
        company_vat = os.environ.get("INVOICEXPRESS_COMPANY_VAT")
        if not account_name or not api_key or not company_vat:
            self.skipTest(
                "Set INVOICEXPRESS_ACCOUNT_NAME, INVOICEXPRESS_API_KEY "
                "and INVOICEXPRESS_COMPANY_VAT to run this live test."
            )
        company = self.env.company
        company.write({"country_id": self.env.ref("base.pt").id, "vat": company_vat})
        journal = self.env["account.journal"].create(
            {
                "name": "InvoiceXpress Live Test",
                "type": "sale",
                "company_id": company.id,
                "invoicexpress_account_name": account_name,
                "invoicexpress_api_key": api_key,
            }
        )
        provider = self.env["account.provider.invoicexpress"]
        try:
            response = provider._call(journal, "taxes.json", raise_errors=False)
        except ValueError:
            raise AssertionError("InvoiceXpress did not return valid JSON.") from None
        except requests.RequestException:
            raise AssertionError("Could not connect to InvoiceXpress.") from None
        self.assertEqual(
            response.status_code, 200, "InvoiceXpress tax list request failed."
        )
        try:
            payload = response.json()
        except ValueError:
            raise AssertionError("InvoiceXpress did not return valid JSON.") from None
        self.assertIsInstance(
            payload.get("taxes") if isinstance(payload, dict) else None, list
        )
