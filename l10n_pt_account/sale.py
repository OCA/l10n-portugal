# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 Thinkopen Solutions, Lda. All Rights Reserved
#    http://www.thinkopensolutions.com.
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api, _


class SaleOrder(models.Model):
    _inherit="sale.order"

    hide_discounts = fields.Boolean(
        string="Hide Discounts", required=False,
        help="If True is visible in report.")

    ## FIX problem of multicompany.
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
            same_partner = lambda inv: inv.partner_id == order.partner_id
            filtered_invoices = order.invoice_ids.filtered(same_partner)
            order.update({
                'invoice_count': len(set(filtered_invoices)),
                'invoice_ids': filtered_invoices.ids,
            })
