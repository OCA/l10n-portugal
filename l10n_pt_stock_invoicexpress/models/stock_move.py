# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    l10npt_invoicexpress_tax_id = fields.Many2one(
        "account.tax",
        string="InvoiceXpress Tax",
        compute="_compute_l10npt_invoicexpress_tax_id",
        help="Tax used for the InvoiceXpress transport document line.",
    )

    @api.depends(
        "sale_line_id.tax_ids",
        "product_id.taxes_id",
        "product_id.taxes_id.type_tax_use",
        "company_id.account_sale_tax_id",
    )
    def _compute_l10npt_invoicexpress_tax_id(self):
        """
        Tax to send for this move on an InvoiceXpress transport document.

        Fallback chain: sale order line tax, product sale tax,
        company's default sale tax.
        """
        for move in self:
            tax = move.sale_line_id.tax_ids[:1]
            if not tax:
                tax = move.product_id.taxes_id.filtered(
                    lambda tax_rec, move=move: tax_rec.type_tax_use == "sale"
                    and tax_rec.company_id == move.company_id
                )[:1]
            if not tax:
                tax = move.company_id.account_sale_tax_id
            move.l10npt_invoicexpress_tax_id = tax

    def _prepare_invoicexpress_line_vals(self):
        self.ensure_one()
        tax = self.l10npt_invoicexpress_tax_id
        tax_detail = {"name": tax.name} if tax else {}

        # Build description
        description = self.description_picking or self.product_id.name or ""
        if self.picking_id.picking_type_id.invoicexpress_include_uom:
            description = f"{description} ({self.product_uom.name})"

        return {
            "name": self.product_id.default_code or self.product_id.display_name,
            "description": description,
            # TODO: add an option to allow having the prices set?
            "unit_price": 0.0,  # self.sale_line_id.price_unit,
            "quantity": self.quantity,
            "discount": self.sale_line_id.discount,
            "tax": tax_detail,
        }
