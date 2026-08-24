# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    l10npt_has_tax_exempt_lines = fields.Boolean(
        compute="_compute_l10npt_has_tax_exempt_lines"
    )
    l10npt_vat_exempt_reason = fields.Many2one(
        "account.l10n_pt.vat.exempt.reason",
        string="VAT Exempt Reason",
        compute="_compute_l10npt_vat_exempt_reason",
        store=True,
        readonly=False,
        help="VAT exemption reason used on invoices and transport documents "
        "created from this sale order. Defaults from the sales journal.",
    )

    @api.depends("order_line.tax_ids", "order_line.display_type")
    def _compute_l10npt_has_tax_exempt_lines(self):
        for order in self:
            order.l10npt_has_tax_exempt_lines = any(
                not line.display_type and not line.tax_ids.filtered("amount")
                for line in order.order_line
            )

    @api.depends(
        "l10npt_has_tax_exempt_lines",
        "journal_id",
        "journal_id.l10npt_vat_exempt_reason",
    )
    def _compute_l10npt_vat_exempt_reason(self):
        for order in self:
            if (
                order.l10npt_has_tax_exempt_lines
                and not order.l10npt_vat_exempt_reason
                and order.journal_id
            ):
                order.l10npt_vat_exempt_reason = (
                    order.journal_id.l10npt_vat_exempt_reason
                )

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        if self.l10npt_vat_exempt_reason:
            invoice_vals["l10npt_vat_exempt_reason"] = self.l10npt_vat_exempt_reason.id
        return invoice_vals
