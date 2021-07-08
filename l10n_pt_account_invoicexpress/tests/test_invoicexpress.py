from unittest.mock import Mock, patch

import requests

from odoo import fields
from odoo.tests import Form, common


def mock_response(json, status_code=200):
    mock_response = Mock()
    mock_response.json.return_value = json
    mock_response.text = str(json)
    mock_response.status_code = status_code
    return mock_response


@common.tagged("-at_install", "post_install")
class TestInvoiceXpress(common.TransactionCase):
    def setUp(self):
        super().setUp()

        self.company = self.env.company
        self.company.write(
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

    def test_010_get_config_and_base_url(self):
        API = self.env["account.invoicexpress"]
        url = API._build_url(API._get_config(self.company), "dummy.json")
        self.assertEqual(url, "https://ACCOUNT.app.invoicexpress.com/dummy.json")

    @patch.object(requests, "request")
    def test_100_create_invoicexpress_tax(self, mock_request):
        mock_request.return_value = mock_response(
            {
                "tax": {
                    "id": 31540,
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
        self.assertEqual(taxA.invoicexpress_id, "31540")

    @patch.object(requests, "request")
    def test_101_create_invoicexpress_invoice(self, mock_request):
        mock_request.return_value = mock_response(
            {"invoice": {"id": 2137287, "inverted_sequence_number": "MYSEQ/123"}}
        )

        move_form = Form(self.AccountMove.with_context(default_move_type="out_invoice"))
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partnerA

        products = [self.productA, self.productB]

        for product in products:
            with move_form.invoice_line_ids.new() as line_form:
                line_form.product_id = product
        invoice = move_form.save()
        invoice.action_post()

        invoice.action_create_invoicexpress_invoice()
        self.assertTrue(invoice.invoicexpress_id)
