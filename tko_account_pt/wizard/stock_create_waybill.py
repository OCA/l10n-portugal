# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Tiny SPRL (<http://tiny.be>).
#
#    Thinkopen - Portugal & Brasil
#    Copyright (C) Thinkopen Solutions (<http://www.thinkopensolutions.com>).
#
#    $Id$
#
#    This module was developed by ThinkOpen Solutions for OpenERP as a
#    contribution to the community.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version $revnoof the License, or
#    (at your option) any later version.51
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


class stock_picking_waybill_line(osv.osv_memory):
    _name = "stock.picking.waybill.line"
    _rec_name = 'product_id'
    _columns = {
        'product_id': fields.many2one(
            'product.product', string="Product", required=True,
            ondelete='CASCADE'),
        'product_qty': fields.float(
            "Quantity", digits_compute=dp.get_precision('Product UoM'),
            required=True),
        'product_uom': fields.many2one(
            'product.uom', 'Unit of Measure', required=True,
            ondelete='CASCADE'),
        'move_id': fields.many2one('stock.move', "Move", ondelete='CASCADE'),
        'wizard_id': fields.many2one(
            'stock.picking.waybill', string="Wizard", ondelete='CASCADE'),
        'cost': fields.float("Cost", help="Unit Cost for this product line"),
    }


class stock_picking_waybill(osv.osv_memory):
    _name = "stock.picking.waybill"
    _description = "Creating Waybill From Picking Wizard"

    _columns = {
        'type_waybill': fields.selection(
            [("remessa", "Remessa"),
             ("transporte", "Transporte"),
             ("devolucao", "Devolução")],
            "Waybill Type", required=True, select=1),
        'with_cost': fields.boolean(
            "With Cost?",
            help="If true the waybill will be created with product cost."),
        'group': fields.boolean("Group by partner"),
    }

    _defaults = {
        'with_cost': True,
        'type_waybill': 'remessa'
    }

    def view_init(self, cr, uid, fields_list, context=None):
        if context is None:
            context = {}
        res = super(stock_picking_waybill, self).view_init(
            cr, uid, fields_list, context=context)
        pick_obj = self.pool.get('stock.picking')
        count = 0
        active_ids = context.get('active_ids', [])
        for pick in pick_obj.browse(cr, uid, active_ids, context=context):
            if pick.invoice_state == 'invoiced' or \
               pick.waybill_state != 'none':
                count += 1
        if len(active_ids) == 1 and count:
            raise osv.except_osv(
                _('Warning !'),
                _('This picking list does not require creating waybill.'))
        if len(active_ids) == count:
            raise osv.except_osv(
                _('Warning !'),
                _('None of these picking lists require creating waybill.'))
        return res

    def default_get(self, cr, uid, fields, context=None):
        res = {}
        if context is None:
            context = {}
        res = super(stock_picking_waybill, self).default_get(
            cr, uid, fields, context=context)
        picking_ids = context.get('active_ids', [])
        if not picking_ids or \
           context.get('active_model') != 'stock.picking' or \
           len(picking_ids) != 1:
            # Partial Picking Processing may only be done for
            # one picking at a time
            return res
        picking_id, = picking_ids
        picking_obj = self.pool.get('stock.picking')
        picking = picking_obj.browse(cr, uid, picking_id, context=context)
        picking_code = picking.picking_type_id.code
        if picking_code == 'outgoing' and picking.name.find('-return') > 0:
            res['type_waybill'] = 'devolucao'
        if picking_code == 'outgoing' and \
           picking.invoice_state == 'none' and \
           picking.name.find('-return') < 0:
            res['type_waybill'] = 'transporte'
        return res

    def create_waybill(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        waybill_ids = []
        action_model = False
        action = {}
        data_pool = self.pool.get('ir.model.data')
        picking_obj = self.pool.get('stock.picking')
        fields = ['date', 'type_waybill', 'with_cost', 'move_ids', 'group']
        onshipdata_obj = self.read(cr, uid, ids, fields)
        active_ids = context.get('active_ids', [])
        context['type_waybill'] = onshipdata_obj[0]['type_waybill']
        context['with_cost'] = onshipdata_obj[0]['with_cost']
        type_waybill = onshipdata_obj[0]['type_waybill']
        group = onshipdata_obj[0]['group']
        res = picking_obj.action_waybill_create(
            cr, uid, active_ids, group, context)
        waybill_ids += res.values()
        if not waybill_ids:
            raise osv.except_osv(_('Error'), _('No Waybills were created.'))
        # Get action for waybills
        key = 'action_account_guia_{0}_form'.format(type_waybill)
        action_model, action_id = data_pool.get_object_reference(
            cr, uid, 'tko_account_pt', key)
        if action_model:
            action_pool = self.pool.get(action_model)
            action = action_pool.read(cr, uid, action_id, context=context)
            domain = [('id', 'in', waybill_ids)]
            action['domain'] = str(domain)
        return action
