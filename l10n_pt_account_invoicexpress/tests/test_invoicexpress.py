import json
from unittest.mock import patch

import requests

from odoo import fields
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
        # Ensure Journal is configured
        self.sale_journals.write({"invoicexpress_doc_type": "invoice_receipt"})
        # Create the Invoice
        move_form = Form(self.AccountMove.with_context(default_move_type="out_invoice"))
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partnerA
        products = [self.productA, self.productB]

        for product in products:
            with move_form.invoice_line_ids.new() as line_form:
                line_form.product_id = product
        invoice = move_form.save()
        invoice.action_post()
        self.assertEqual(invoice.invoicexpress_doc_type, "invoice_receipt")
        self.assertEqual(invoice.invoicexpress_id, "12345678")
        self.assertEqual(invoice.name, "FR MYSEQ/123")

    @patch("requests.request")
    def test_debit_note_links_invoicexpress_original(self, mock_request):
        mock_request.side_effect = mock_request_side_effect
        # Ensure Journal is configured
        self.sale_journals.write({"invoicexpress_doc_type": "invoice_receipt"})
        move_form = Form(self.AccountMove.with_context(default_move_type="out_invoice"))
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partnerA
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.productA
        origin = move_form.save()
        origin.action_post()
        origin_invx_id = origin.invoicexpress_id
        self.assertTrue(origin_invx_id)
        mock_request.reset_mock()

        wizard = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=origin.ids)
            .create({"copy_lines": True, "reason": "Adjustment"})
        )
        action = wizard.create_debit()
        debit = self.env["account.move"].browse(action["res_id"])
        debit.action_post()

        self.assertEqual(debit.invoicexpress_doc_type, "debit_note")
        self.assertEqual(debit.invoicexpress_id, "87654321")
        self.assertEqual(debit.name, "ND MYSEQ/456")
        create_call = next(
            call
            for call in mock_request.call_args_list
            if call.args[0] == "POST" and call.args[1].endswith("/debit_notes.json")
        )
        data = json.loads(create_call.kwargs["data"])
        self.assertEqual(data["invoice"]["owner_invoice_id"], origin_invx_id)
        self.assertNotIn("raw_owner_invoice", data["invoice"])
        self.assertNotIn("raw_owner_invoice", data)
        finalize_call = next(
            call
            for call in mock_request.call_args_list
            if call.args[0] == "PUT"
            and "/debit_notes/87654321/change-state.json" in call.args[1]
        )
        self.assertEqual(
            json.loads(finalize_call.kwargs["data"]),
            {"invoice": {"state": "finalized"}},
        )

    @patch("requests.request")
    def test_debit_note_external_original_uses_raw_reference(self, mock_request):
        mock_request.side_effect = mock_request_side_effect
        # Post the original before enabling InvoiceXpress on its journal
        self.sale_journals.write({"invoicexpress_doc_type": "none"})
        move_form = Form(self.AccountMove.with_context(default_move_type="out_invoice"))
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partnerA
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.productA
        origin = move_form.save()
        origin.action_post()
        origin_name = origin.name
        self.assertFalse(origin.invoicexpress_id)

        journal = origin.journal_id
        journal.write({"invoicexpress_doc_type": "invoice_receipt"})
        mock_request.reset_mock()
        wizard = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=origin.ids)
            .create(
                {
                    "copy_lines": True,
                    "reason": "Adjustment",
                    "journal_id": journal.id,
                }
            )
        )
        action = wizard.create_debit()
        debit = self.env["account.move"].browse(action["res_id"])
        debit.action_post()

        self.assertEqual(debit.invoicexpress_doc_type, "debit_note")
        create_call = next(
            call
            for call in mock_request.call_args_list
            if call.args[0] == "POST" and call.args[1].endswith("/debit_notes.json")
        )
        data = json.loads(create_call.kwargs["data"])
        self.assertEqual(data["invoice"]["raw_owner_invoice"], origin_name)
        self.assertNotEqual(data["invoice"]["raw_owner_invoice"], debit.ref)
        self.assertNotIn("owner_invoice_id", data["invoice"])
