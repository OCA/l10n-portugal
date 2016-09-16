# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./
from openerp.osv import fields, osv
from openerp.tools.translate import _


class StockSimplifiedOnshipping(osv.osv_memory):
    _name = "stock.simplified.invoice.onshipping"
    _description = "Account PT Stock Simplified Invoice Onshipping"

    def _get_journal(self, cr, uid, context=None):
        res = self._get_journal_id(cr, uid, context=context)
        if res:
            return res[0][0]
        return False

    def _get_journal_id(self, cr, uid, context=None):
        if context is None:
            context = {}

        model = context.get('active_model')
        if not model or 'stock.picking' not in model:
            return []

        model_pool = self.pool.get(model)
        journal_obj = self.pool.get('account.journal')
        res_ids = context and context.get('active_ids', [])
        vals = []
        browse_picking = model_pool.browse(cr, uid, res_ids, context=context)

        for pick in browse_picking:
            if not pick.move_lines:
                continue
            src_usage = pick.move_lines[0].location_id.usage
            dest_usage = pick.move_lines[0].location_dest_id.usage
            type = pick.type
            if type == 'out' and dest_usage == 'supplier':
                journal_type = 'purchase_refund'
            elif type == 'out' and dest_usage == 'customer':
                journal_type = 'sale'
            elif type == 'in' and src_usage == 'supplier':
                journal_type = ('purchase',)
            elif type == 'in' and src_usage == 'customer':
                journal_type = 'sale_refund'
            else:
                journal_type = 'sale'

            value = journal_obj.search(cr, uid, [('type', '=', journal_type)])
            for jr_type in journal_obj.browse(cr, uid, value, context=context):
                t1 = jr_type.id, jr_type.name
                if t1 not in vals:
                    vals.append(t1)
        if not vals:
            raise osv.except_osv(
                _('Warning !'),
                _('Either there are no moves linked to the picking or '
                  'Accounting Journals are misconfigured!'))

        return vals

    _columns = {
        'journal_id': fields.selection(
            _get_journal_id, 'Destination Journal', required=True),
        'group': fields.boolean("Group by partner"),
        'invoice_date': fields.date('Invoiced date'),
    }

    _defaults = {
        'journal_id': _get_journal,
    }

    def view_init(self, cr, uid, fields_list, context=None):
        if context is None:
            context = {}
        res = super(StockSimplifiedOnshipping, self).view_init(
            cr, uid, fields_list, context=context)
        pick_obj = self.pool.get('stock.picking')
        count = 0
        active_ids = context.get('active_ids', [])
        for pick in pick_obj.browse(cr, uid, active_ids, context=context):
            if pick.invoice_state != '2binvoiced'\
               or pick.waybill_state != 'none':
                count += 1
        if len(active_ids) == 1 and count:
            raise osv.except_osv(
                _('Warning !'),
                _('This picking list does not require invoicing or '
                  'already created a waybill.'))
        if len(active_ids) == count:
            raise osv.except_osv(
                _('Warning !'),
                _('None of these picking lists require invoicing or '
                  'already created a waybill.'))
        return res

    def open_simplified(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        invoice_ids = []
        data_pool = self.pool.get('ir.model.data')
        res = self.create_simplified_invoice(cr, uid, ids, context=context)
        invoice_ids += res.values()
        action_model = False
        action = {}
        if not invoice_ids:
            raise osv.except_osv(_('Error'), _(
                'No Simplified Invoices were created.'))
        action_model, action_id = data_pool.get_object_reference(
            cr, uid, 'l10n_pt_account', "action_simplified_invoice_tree")
        if action_model:
            action_pool = self.pool.get(action_model)
            action = action_pool.read(cr, uid, action_id, context=context)
            action['domain'] = str([('id', 'in', invoice_ids)])
        return action

    def create_simplified_invoice(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        picking_pool = self.pool.get('stock.picking')
        onshipdata_obj = self.read(
            cr, uid, ids, ['journal_id', 'group', 'invoice_date', 'origin'])
        if context.get('new_picking', False):
            onshipdata_obj['id'] = onshipdata_obj.new_picking
            onshipdata_obj[ids] = onshipdata_obj.new_picking
        context['date_inv'] = onshipdata_obj[0]['invoice_date']
        active_ids = context.get('active_ids', [])
        res = picking_pool.action_invoice_create(cr, uid, active_ids,
                                                 journal_id=onshipdata_obj[
                                                     0]['journal_id'],
                                                 group=onshipdata_obj[
                                                     0]['group'],
                                                 type='simplified_invoice',
                                                 context=context)
        return res
