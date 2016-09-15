##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from openerp import models, api, fields, _
from operator import itemgetter


class SaleAdvancePaymentInvoice(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    date_invoice = fields.Date(
        string='Invoice date', required=True, default=fields.Date.today)

    @api.multi
    def _prepare_advance_invoice_vals():
        res = super(SaleAdvancePaymentInvoice, self)._prepare_advance_invoice_vals()
        for order_id, invoice_vals in res:
            invoice_vals['date_invoice'] = self.date_invoice
        return res

    @api.multi
    def create_invoices(self):
        """ create invoices for the active sales orders """
        wizard = self
        if wizard.advance_payment_method == 'all':
            # create the final invoices of the active sales orders
            res = self.manual_invoice_with_date()
            if self._context.get('open_invoices'):
                return res
            return {'type': 'ir.actions.act_window_close'}
        else:
            return super(SaleAdvancePaymentInvoice, self).create_invoices()

    @api.multi
    def manual_invoice_with_date(self):
        wizard = self
        sale_obj = self.env['sale.order']
        mod_obj = self.env['ir.model.data']
        sale_ids = self._context.get('active_ids', [])

        orders = sale_obj.browse(sale_ids)
        get_invoices = itemgetter('invoice_ids')
        invoices0 = orders.mapped(get_invoices)
        orders.with_context(date_invoice=wizard.date_invoice).action_invoice_create()
        invoices1 = sale_obj.browse(sale_ids).mapped(get_invoices)
        # determine newly created invoices
        new_invoices = invoices1 - invoices0
        first_new_invoice_id = new_invoices.ids[0] if new_invoices else False

        view_id = mod_obj.xmlid_to_res_id('account.invoice_form')
        return {
            'name': _('Customer Invoices'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [view_id],
            'res_model': 'account.invoice',
            'context': "{'type':'out_invoice'}",
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': first_new_invoice_id,
        }