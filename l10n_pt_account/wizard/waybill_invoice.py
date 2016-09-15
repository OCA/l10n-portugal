# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
from openerp.osv import fields, osv
from openerp.tools.translate import _


class waybill_invoice(osv.osv_memory):
    _name = "waybill.invoice"
    _description = "Account PT Invoice Waybill"
    
    def _get_journal_id(self, cr, uid, context=None):
        if context is None:
            context = {}
        vals=[]
        journal_obj = self.pool.get('account.journal')
        value = journal_obj.search(cr, uid, [('type','=','sale' )])
        for jr_type in journal_obj.browse(cr, uid, value, context=context):
            t1 = jr_type.id,jr_type.name
            if t1 not in vals:
                vals.append(t1)
#        if not vals:
#            raise osv.except_osv(_('Warning !'), _('Accounting Journals are misconfigured!'))
        return vals

    _columns = {
        'journal_id': fields.selection(_get_journal_id, 'Destination Journal',required=True),
        'group': fields.boolean("Group by partner"),
        'invoice_date': fields.date('Invoiced date'),
        #'force_open': fields.boolean('Force Open', help='Select to force the opening of this document, even if there are older drafts or created ones.\nIt doesn\'t force opening if there are higher ones.')
    }
    
    def view_init(self, cr, uid, fields_list, context=None):
        if context is None:
            context = {}
        res = super(waybill_invoice, self).view_init(cr, uid, fields_list, context=context)
        guia_obj = self.pool.get('account.guia')
        count = 0
        active_ids = context.get('active_ids',[])
        for guia in guia_obj.browse(cr, uid, active_ids, context=context):
            if guia.invoice_state != 'none' or guia.state!='arquivada' or guia.tipo not in ('remessa','transporte'):
                count += 1
        if len(active_ids) == 1 and count:
            raise osv.except_osv(_('Warning !'), _('This waybill is not in state "arquivada" or is already invoiced or not type "Remessa" or "Transporte"'))
        if len(active_ids) == count:
            raise osv.except_osv(_('Warning !'), _('The waybills selected are not in state draft or are already invoiced or not type "Remessa" or "Transporte"'))
        return res

    
    def open_invoice(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        guia_pool = self.pool.get('account.guia')
        waybilldata_obj = self.read(cr, uid, ids, ['journal_id', 'group', 'invoice_date','force_open'])
        context['date_inv'] = waybilldata_obj[0]['invoice_date']
        context['type'] = 'out_invoice'
        context['group'] = waybilldata_obj[0]['group']
        active_ids = context.get('active_ids', [])
        active_waybill = guia_pool.browse(cr, uid, context.get('active_id',False), context=context)
        return guia_pool.action_invoice_onguia(cr, uid, active_ids, context=context)

waybill_invoice()

class waybill_simplified_invoice(osv.osv_memory):
    _name = "waybill.simplified.invoice"
    _inherit = "waybill.invoice"
    _description = "Account PT Simplified Invoice Waybill"
    
    def open_simplified_invoice(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        guia_pool = self.pool.get('account.guia')
        waybilldata_obj = self.read(cr, uid, ids, ['journal_id', 'group', 'invoice_date','force_open'])
        context['date_inv'] = waybilldata_obj[0]['invoice_date']
        context['type'] = 'simplified_invoice'
        context['group'] = waybilldata_obj[0]['group']
        active_ids = context.get('active_ids', [])
        active_waybill = guia_pool.browse(cr, uid, context.get('active_id',False), context=context)
        res = guia_pool.action_invoice_onguia(cr, uid, active_ids, context=context)
        return res
