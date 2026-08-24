from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
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

    def _get_exempt_reason(self, code="M01"):
        reason = self.env["account.l10n_pt.vat.exempt.reason"].search(
            [("code", "=", code)], limit=1
        )
        if not reason:
            reason = self.env["account.l10n_pt.vat.exempt.reason"].create(
                {"name": f"Reason {code}", "code": code}
            )
        return reason

    def _create_exempt_product(self, name="Exempt Product"):
        tax = self.AccountTax.create(
            {
                "name": "IVA0",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": 0.0,
            }
        )
        tax.invoicexpress_id = "12345"
        product = self.ProductProduct.create(
            {"name": name, "list_price": "10.0", "is_storable": True}
        )
        product.write({"taxes_id": [(6, 0, [tax.id])]})
        return product, tax

    def _sale_journal(self):
        journal = self.sale_journals.filtered(lambda j: j.company_id == self.company)[
            :1
        ]
        self.assertTrue(journal, "No sales journal for the test company")
        return journal

    def _create_sale_order(self, product, tax, reason=None):
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partnerA.id,
                "journal_id": self._sale_journal().id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_id": product.uom_id.id,
                            "product_uom_qty": 1,
                            "price_unit": 10.0,
                            "tax_ids": [(6, 0, [tax.id])],
                        },
                    )
                ],
            }
        )
        if reason:
            sale_order.l10npt_vat_exempt_reason = reason
        return sale_order

    def _create_picking(self, product, quantity=1):
        """Create and prepare a picking with the given product."""
        self.env["stock.quant"]._update_available_quantity(
            product, self.warehouse.lot_stock_id, quantity
        )
        picking_form = Form(self.StockPicking)
        picking_form.partner_id = self.partnerA
        picking_form.picking_type_id = self.warehouse.out_type_id
        picking_form.scheduled_date = fields.Datetime.now() + timedelta(days=1)
        with picking_form.move_ids.new() as move:
            move.product_id = product
            move.product_uom_qty = quantity
        picking = picking_form.save()
        picking.action_confirm()
        picking.action_assign()
        picking.move_line_ids.filtered(
            lambda ml: ml.product_id == product
        ).quantity = float(quantity)
        return picking

    @patch("requests.request")
    def test_110_picking_prepare_invoicexpress_vals_tax_exemption(self, mock_request):
        """A transport guide with exempt lines sends tax_exemption."""
        mock_request.side_effect = mock_request_side_effect
        product, _tax = self._create_exempt_product()
        reason = self._get_exempt_reason("M01")
        picking = self._create_picking(product)
        picking.l10npt_vat_exempt_reason = reason

        vals = picking._prepare_invoicexpress_vals()
        self.assertIn("tax_exemption", vals[picking.invoicexpress_doc_type])
        self.assertEqual(vals[picking.invoicexpress_doc_type]["tax_exemption"], "M01")

    def test_120_sale_order_vat_exempt_reason_from_journal(self):
        """Sale order inherits VAT exempt reason from its sales journal."""
        reason = self._get_exempt_reason("M01")
        journal = self._sale_journal()
        journal.l10npt_vat_exempt_reason = reason
        product, tax = self._create_exempt_product()

        sale_order = self._create_sale_order(product, tax)
        self.assertTrue(sale_order.l10npt_has_tax_exempt_lines)
        self.assertEqual(sale_order.l10npt_vat_exempt_reason, reason)

    def test_130_delivery_vat_exempt_reason_from_sale_order(self):
        """Delivery inherits VAT exempt reason from the related sale order."""
        reason = self._get_exempt_reason("M01")
        product, tax = self._create_exempt_product()

        sale_order = self._create_sale_order(product, tax, reason=reason)
        sale_order.action_confirm()

        self.assertEqual(len(sale_order.picking_ids), 1, "A delivery should be created")
        delivery = sale_order.picking_ids
        delivery.move_ids.quantity = 1.0
        self.assertTrue(delivery.l10npt_has_tax_exempt_lines)
        self.assertEqual(delivery.l10npt_vat_exempt_reason, reason)

    @patch("requests.request")
    def test_140_delivery_tax_exemption_missing_raises(self, mock_request):
        """A delivery with exempt lines requires a VAT exemption reason."""
        mock_request.side_effect = mock_request_side_effect
        product, _tax = self._create_exempt_product()
        picking = self._create_picking(product)

        with self.assertRaises(UserError):
            picking.button_validate()

    def test_150_invoice_inherits_sale_order_vat_exempt_reason(self):
        """Invoices created from a sale order keep its VAT exemption reason."""
        reason = self._get_exempt_reason("M01")
        product, tax = self._create_exempt_product()

        sale_order = self._create_sale_order(product, tax, reason=reason)
        invoice_vals = sale_order._prepare_invoice()
        self.assertEqual(invoice_vals["l10npt_vat_exempt_reason"], reason.id)
