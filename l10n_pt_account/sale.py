# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from openerp import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    hide_discounts = fields.Boolean(
        string="Hide Discounts", required=False,
        help="If True is visible in report.")

    # FIX problem of multicompany.
    @api.onchange('company_id')
    def onchange_company_id(self):
        if not self.partner_id or not self.company_id:
            return
        partner_company = self.partner_id.company_id
        if partner_company and partner_company != self.company_id:
            raise UserWarning(
                _('Company must be iqual to company of partner!'))
        query = [('company_id', '=', self.company_id.id)]
        warehouse = self.env['stock.warehouse'].search(query, limit=1)
        if warehouse:
            self.warehouse_id = warehouse

    @api.depends('state', 'order_line.invoice_status')
    def _get_invoiced(self):
        """ Fix problem in core odoo code, which is returning unrelated
        credit notes"""
        super(SaleOrder, self)._get_invoiced()
        for order in self:
            filtered_invoices = order.invoice_ids.filtered(
                lambda inv: inv.partner_id == order.partner_id)
            order.update({
                'invoice_count': len(set(filtered_invoices)),
                'invoice_ids': filtered_invoices.ids,
            })
