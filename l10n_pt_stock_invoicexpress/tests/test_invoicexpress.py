from datetime import timedelta
from unittest.mock import Mock, patch

import requests

from odoo import fields
from odoo.tests import Form, common

from odoo.addons.l10n_pt_account_invoicexpress.tests.test_invoicexpress import (
    TestInvoiceXpress,
)


def mock_response(json, status_code=200):
    mock_response = Mock()
    mock_response.json.return_value = json
    mock_response.text = str(json)
    mock_response.status_code = status_code
    return mock_response


@common.tagged("-at_install", "post_install")
class TestInvoiceXpressStock(TestInvoiceXpress):
    def setUp(self):
        super().setUp()
        self.StockPicking = self.env["stock.picking"]

    @patch.object(requests, "request")
    def test_102_create_invoicexpress_picking(self, mock_request):
        mock_request.return_value = mock_response(
            {"transport": {"id": 12345678, "inverted_sequence_number": "MYSEQ/123"}}
        )
        stock_location = self.env.ref("stock.stock_location_stock")
        self.warehouse = self.env["stock.warehouse"].search(
            [("lot_stock_id", "=", stock_location.id)], limit=1
        )
        # Setup defaults for Operation Types
        self.warehouse.company_id._update_default_doctype()
        # Create a new picking with one product
        picking_form = Form(self.StockPicking)
        picking_form.partner_id = self.partnerA
        picking_form.picking_type_id = self.warehouse.out_type_id
        scheduled_date = fields.Datetime.now() + timedelta(days=1)
        picking_form.scheduled_date = scheduled_date
        picking_form.origin = "Picking-Test"
        with picking_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.productA
            move_line.product_uom_qty = 2
        self.delivery_order = picking_form.save()
        self.assertTrue(self.delivery_order.scheduled_date)

        self.assertEqual(
            self.delivery_order.partner_id.country_id,
            self.pt_country,
            "Country is Portugal",
        )

        self.delivery_order.action_confirm()
        self.delivery_order.action_assign()
        self.delivery_order.move_line_ids.filtered(
            lambda ml: ml.product_id == self.productA
        ).qty_done = 2.0
        self.assertEqual(
            self.delivery_order.state, "assigned", "Delivery Order assigned"
        )

        self.delivery_order.button_validate()
        self.assertTrue(self.delivery_order.invoicexpress_id)
