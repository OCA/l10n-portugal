from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import Form, common

from odoo.addons.l10n_pt_account_invoicexpress.tests.invoicexpress_mock import (
    mock_request_side_effect,
)
from odoo.addons.l10n_pt_account_invoicexpress.tests.test_invoicexpress import (
    TestInvoiceXpress,
)


@common.tagged("-at_install", "post_install")
class TestInvoiceXpressStock(TestInvoiceXpress):
    def setUp(self):
        super().setUp()
        self.StockPicking = self.env["stock.picking"]
        stock_location = self.env.ref("stock.stock_location_stock")
        self.warehouse = self.env["stock.warehouse"].search(
            [
                ("lot_stock_id", "=", stock_location.id),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        if not self.warehouse:
            # Create a warehouse for the test company if none exists
            self.warehouse = self.env["stock.warehouse"].create(
                {
                    "name": "Test Warehouse",
                    "company_id": self.company.id,
                    "lot_stock_id": stock_location.id,
                }
            )
        # Setup defaults for Operation Types
        self.warehouse.company_id._update_default_doctype()
        self.warehouse.out_type_id.invoicexpress_doc_type = "transport"

    @patch("requests.request")
    def test_102_create_invoicexpress_picking(self, mock_request):
        mock_request.side_effect = mock_request_side_effect
        # Create a new picking with one product
        picking_form = Form(self.StockPicking)
        picking_form.partner_id = self.partnerA
        picking_form.picking_type_id = self.warehouse.out_type_id
        scheduled_date = fields.Datetime.now() + timedelta(days=1)
        picking_form.scheduled_date = scheduled_date
        picking_form.origin = "Picking-Test"
        with picking_form.move_ids.new() as move_line:
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
        ).quantity = 2.0
        self.assertEqual(
            self.delivery_order.state, "assigned", "Delivery Order assigned"
        )

        self.delivery_order.button_validate()
        self.assertTrue(self.delivery_order.invoicexpress_id)
