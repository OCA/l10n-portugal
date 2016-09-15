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

from openerp.osv import fields, osv
from openerp.tools.translate import _


class sale_order(osv.osv):
    _inherit = "sale.order"

    def _prepare_order_picking(self, cr, uid, order, context=None):
        dict = super(sale_order, self)\
            ._prepare_order_picking(cr, uid, order, context)
        dict.update({'waybill_state': 'none'})
        return dict


class stock_picking(osv.osv):
    _description = "Delivery Orders"
    _inherit = 'stock.picking'

    def _invoice_hook(self, cursor, user, picking, invoice_id):
        sale_obj = self.pool.get('sale.order')
        order_line_obj = self.pool.get('sale.order.line')
        invoice_obj = self.pool.get('account.invoice')
        invoice_line_obj = self.pool.get('account.invoice.line')
        if picking.sale_id:
            sale_obj.write(cursor, user, [picking.sale_id.id], {
                'invoice_ids': [(4, invoice_id)],
            })
            for sale_line in picking.sale_id.order_line:
                if sale_line.product_id.type == 'service'\
                   and not sale_line.invoiced:
                    vals = order_line_obj\
                        ._prepare_order_line_invoice_line(
                            cursor, user, sale_line, False)
                    vals['invoice_id'] = invoice_id
                    invoice_line_id = invoice_line_obj\
                        .create(cursor, user, vals)
                    order_line_obj.write(
                        cursor, user, [sale_line.id], {
                            'invoice_lines': [(6, 0, [invoice_line_id])],
                        }
                    )
                    invoice_obj.button_compute(cursor, user, [invoice_id])
        return

    def _invoice_line_hook(self, cursor, user, move_line, invoice_line_id):
        if move_line.sale_line_id:
            line_vals = {'invoice_lines': [(4, invoice_line_id)]}
            move_line.sale_line_id.write(line_vals)
        return

    def copy(self, cr, uid, id, default={}, context=None):
        if context is None:
            context = {}
        default.update({
            'waybill_state': 'none',
            'waybill_id': False,
        })
        return super(stock_picking, self).copy(cr, uid, id, default, context)

    def _type_picking(self, cr, uid, ids, prop, unknow_none, context):
        res = {}
        for picking in self.browse(cr, uid, ids, context):
            if picking.name.find('-return') > 0:
                res[picking.id] = 'return'
            else:
                res[picking.id] = 'none'
        return res

    def _get_sale_orders(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        order_pool = self.pool['sale.order']
        for picking in self.browse(cr, uid, ids, context=context):
            query = [('procurement_group_id', '=', picking.group_id.id)]
            res[picking.id] = order_pool.search(cr, uid, query)
        return res

    def _sale_order_invoiced(self, cr, uid, ids,
                             field_name, arg, context=None):
        res = {}
        for picking in self.browse(cr, uid, ids, context=context):
            res[picking.id] = all(order.invoice_status == 'invoiced'
                                  for order in picking.sale_order_ids)
        return res

    _columns = {
        'waybill_state': fields.selection(
            [
                ('waybilled', 'Waybilled'),
                ("none", "Not Applicable"),
            ], "Waybill Control", readonly=True),
        'waybill_id': fields.many2one('account.guia', "Waybill"),
        'type_picking': fields.function(
            _type_picking, method=True, string="Type Picking", type="char"),
        'sale_order_ids': fields.function(
            _get_sale_orders, type='many2many', relation='sale.order'),
        'invoice_state': fields.function(
            _sale_order_invoiced, type='char', string='Invoice State'),
    }

    _defaults = {
        'waybill_state': 'none'
    }

    def _prepare_invoice_line(self, cr, uid, group, picking,
                              move_line, invoice_id,
                              invoice_vals, context=None):
        """ Inherit the original function of the 'stock' module in order to correct
            the account in simplified invoice
        """
        invoice_line_vals = super(stock_picking, self)._prepare_invoice_line(
            cr, uid, group, picking, move_line, invoice_id, invoice_vals,
            context=context)
        if invoice_vals['type'] in ('simplified_invoice'):
            account_id = move_line.product_id.property_account_income_id.id
            if not account_id:
                account_id = move_line.product_id.categ_id\
                    .property_account_income_categ_id.id
            if invoice_vals['fiscal_position_id']:
                fp_obj = self.pool.get('account.fiscal.position')
                fiscal_position = fp_obj.browse(
                    cr, uid, invoice_vals['fiscal_position_id'],
                    context=context)
                account_id = fp_obj.map_account(
                    cr, uid, fiscal_position, account_id)
            if move_line.product_uos:
                uom_id = move_line.product_uos.id
            else:
                uom_id = False
            if not uom_id:
                uom_id = move_line.product_uom.id
            invoice_line_vals.update({
                'account_id': account_id,
                'uom_id': uom_id,
            })
        return invoice_line_vals

    def _prepare_invoice(self, cr, uid, picking, partner,
                         inv_type, journal_id, context=None):
        """ Inherit the original function of the 'stock' module
            in order to correct some values if the picking has been
            generated by a sales order. account_id from order partner_id,
            fiscal_position from order or property of order partner_id
        """
        invoice_vals = super(stock_picking, self)._prepare_invoice(
            cr, uid, picking, partner, inv_type, journal_id, context=context)
        sale = picking.sale_id
        if sale:
            if sale.fiscal_position_id:
                invoice_vals['fiscal_position_id'] = sale.fiscal_position_id.id
            else:
                invoice_vals['fiscal_position_id'] = sale.partner_id\
                    .property_account_position_id.id
            invoice_vals['account_id'] = sale.partner_id\
                .property_account_receivable.id
        return invoice_vals

    def _get_partner_to_invoice(self, cr, uid, picking, context=None):
        """ Inherit the original function of the 'stock' module
            We select the partner_invoice_id of the sales order
            as the partner of the customer invoice
        """
        if picking.sale_id:
            return picking.sale_id.partner_invoice_id
        return super(stock_picking, self)._get_partner_to_invoice(
            cr, uid, picking, context=context)

    def _get_partner_to_waybill(self, cr, uid, picking, context=None):
        """ We select the partner_invoice_id of the sales order
            as the partner of the customer invoice
        """
        if picking.sale_id:
            return picking.sale_id.partner_shipping_id
        return picking.partner_id

    def action_waybill_create(self, cr, uid, ids, group=False,
                              type_waybill=None, with_cost=None,
                              context=None):
        """
        Creates waybill based on picking
        """
        if context is None:
            context = {}
        if type_waybill is None:
            type_waybill = context.get('type_waybill', False)
        if with_cost is None:
            with_cost = context.get('with_cost', False)
        waybill_group = {}
        res = {}
        guia_obj = self.pool.get('account.guia')
        guia_line_obj = self.pool.get('account.linha.guia')
        stock_move_obj = self.pool.get('stock.move')
        for picking in self.browse(cr, uid, ids, context=context):
            # Confirm if picking is done
            if picking.state != 'done'\
               or picking.invoice_state == 'invoiced'\
               or picking.waybill_state != 'none':
                continue
            # If invoice not aplicable only create transport waybills
            if picking.invoice_state == 'none'\
               and type_waybill != 'transporte':
                continue
            # If picking is return only create devolucao waybills
            if picking.type_picking == 'return'\
               and type_waybill != 'devolucao':
                continue
            partner = picking.partner_id
            if not partner:
                raise osv.except_osv(
                    _('Error, no partner !'),
                    _('Please put a partner on the picking list '
                      'if you want to generate waybill.'))
            # Group pickings when same partner and same address
            if group and partner.id in waybill_group:
                guia_id = waybill_group[partner.id]['guia_id']
                waybill = guia_obj.browse(cr, uid, guia_id)
                waybill_vals = {
                    'origin': (waybill.origin or '') + ', ' +
                              (picking.name or '') +
                              (picking.origin and
                                  (':' + picking.origin) or ''),
                    'stock_picking_ids': [(4, picking.id)],
                    'observacoes': picking.name or ''
                }
                if waybill.sale_id:
                    if picking.sale_id.client_order_ref:
                        waybill_vals['name'] += ', ' + picking.sale_id\
                            .client_order_ref
                    if waybill.sale_id.id == picking.sale_id.id:
                        waybill_vals['sale_id'] = picking.sale_id.id
                guia_obj.write(
                    cr, uid, [guia_id], waybill_vals, context=context)
            else:
                waybill_vals = {
                    'tipo': type_waybill,
                    'partner_id': partner.id,
                    'stock_picking_ids': [(4, picking.id)],
                    'company_id': picking.company_id.id,
                    'origin': picking.name or '',
                    'observacoes': (picking.name and ("Ref Ordens Entrega: " + picking.name) or '')
                }
                if picking.origin:
                    waybill_vals['origin'] = waybill_vals['origin'] + ': ' + picking.origin
                if picking.sale_order_ids:
                    sale_orders = picking.sale_order_ids
                    waybill_vals['name'] = ', '.join((order.client_order_ref or '') for order in sale_orders)
                # Create Waybill
                guia_id = guia_obj.create(cr, uid, waybill_vals, context=context)
                waybill_group[partner.id] = { 'guia_id':guia_id}

            # get move lines selected or if is a group creation get stock moves from picking
            for line in picking.move_lines:
                if line.state == 'cancel':
                    continue
                invoice_vals = stock_move_obj._get_invoice_line_vals(cr, uid, line, partner, 'out_invoice', context=context)
                waybill_lines = { 
                                  'guia_id': guia_id,
                                  'product_id': line.product_id.id,
                                  'uom_id': line.product_id.uom_id.id or False,
                                  'price_unit': 0.0,
                                  'quantity': line.product_qty,
                                  'discount': 0.0,
                                  'name': line.name,
                                  'account_id': partner.property_account_receivable_id.id,
                                  'invoice_line_tax_id': invoice_vals.get('invoice_line_tax_id', False),
                                  'account_analytic_id': invoice_vals.get('account_analytic_id', False),
                                  'move_line_id': line.id,
                                }
                if with_cost:
                    waybill_lines['price_unit'] = invoice_vals.get('price_unit', False)
                    if type_waybill not in ('devolucao'):
                        waybill_lines['discount'] = invoice_vals.get('discount', False)
                # create waybill lines
                guia_line_id = guia_line_obj.create(cr, uid, waybill_lines, context=context)
            res[picking.id] = guia_id
            self.write(cr, uid, [picking.id], {'waybill_id': guia_id, 'waybill_state': 'waybilled'})
        return res

# Redefinition of the new field in order to update the model stock.picking in the orm
# FIXME: this is a temporary workaround because of a framework bug (ref: lp996816). It should be removed as soon as
#        the bug is fixed
class stock_picking_out(osv.osv):
    _inherit = 'stock.picking'
    
    def copy(self, cr, uid, id, default={}, context=None):
        if context is None:
            context = {}
        default.update({
                        'waybill_state': 'none',
                        'waybill_id': False,
                        })
        return super(stock_picking_out, self).copy(cr, uid, id, default, context)
    
    def _type_picking(self, cr, uid, ids, prop, unknow_none, context):
        res={}
        for picking in self.browse(cr, uid, ids, context):
            if picking.name.find('-return') > 0:
                res[picking.id]= 'return'
            else:
                res[picking.id] ='none'
        return res
    _columns = {
                'waybill_state': fields.selection([('waybilled', 'Waybilled'), ("none", "Not Applicable")], "Waybill Control", readonly = True),
                'waybill_id': fields.many2one('account.guia', "Waybill"),
                'type_picking': fields.function(_type_picking, method = True, string="Type Picking", type="char"),
                }
    _defaults = {'waybill_state': 'none'
    }

class StockMove(osv.osv):
    _inherit = 'stock.move'
    
    def _get_invoice_line_vals(self, cr, uid, move, partner, inv_type, context=None):
        fp_obj = self.pool.get('account.fiscal.position')
        # Get account_id
        if inv_type in ('out_invoice', 'out_refund'):
            account_id = move.product_id.property_account_income_id.id
            if not account_id:
                account_id = move.product_id.categ_id.property_account_income_categ_id.id
        else:
            account_id = move.product_id.property_account_expense_id.id
            if not account_id:
                account_id = move.product_id.categ_id.property_account_expense_categ_id.id
        fiscal_position = partner.property_account_position_id
        account_id = fp_obj.map_account(cr, uid, fiscal_position, account_id)

        # set UoS if it's a sale and the picking doesn't have one
        uos_id = move.product_uom.id
        quantity = move.product_uom_qty

        if move.procurement_id.so_line_id:
            price_unit = move.procurement_id.so_line_id.price_unit
            taxes_ids = move.procurement_id.so_line_id.tax_id.ids
        else:
            price_unit = move.product_id.lst_price
            taxes_ids = []

        return {
            'name': move.name,
            'account_id': account_id,
            'product_id': move.product_id.id,
            'uos_id': uos_id,
            'quantity': quantity,
            'price_unit': price_unit,
            'invoice_line_tax_ids': [(6, 0, taxes_ids)],
            'discount': 0.0,
            'account_analytic_id': False,
            'move_id': move.id,
        }
