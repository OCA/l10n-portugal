import json
from unittest.mock import patch

import requests

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import Form, common

from .invoicexpress_mock import mock_request_side_effect, mock_response


@common.tagged("-at_install", "post_install")
class TestInvoiceXpress(common.TransactionCase):
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
        Journal = self.env["account.journal"]
        self.sale_journals = Journal.search([("type", "=", "sale")])

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
        API = self.env["account.invoicexpress"]
        url = API._build_url(API._get_config(self.company), "dummy.json")
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
        taxA.action_invoicexpress_tax_create()
        self.assertEqual(taxA.invoicexpress_id, "12345")

    @patch("requests.request")
    def test_101_create_invoicexpress_invoice(self, mock_request):
        mock_request.side_effect = mock_request_side_effect
        tax = self._make_invoice_tax("IVA23", 23)
        invoice = self._make_invoice_with_taxes(tax, tax)
        invoice.action_post()
        self.assertEqual(invoice.l10n_pt_doc_type, "invoice_receipt")
        self.assertEqual(invoice.l10n_pt_doc_id, "12345678")
        self.assertEqual(invoice.name, "FR MYSEQ/123")
        self.assertNotIn("tax_exemption", self._get_sent_invoice(mock_request))

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

    def _make_invoice_with_taxes(self, *taxes):
        self.sale_journals.write(
            {
                "l10n_pt_doc_provider": "invoicexpress",
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
