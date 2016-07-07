# -*- coding: utf-8 -*-
# Copyright (C) 2012 Thinkopen Solutions, Lda. All Rights Reserved
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp.osv import osv
from openerp.tools.translate import _


class stock_invoice_onshipping(osv.osv_memory):
    _name = "stock.invoice.onshipping"
    _inherit = "stock.invoice.onshipping"

    def view_init(self, cr, uid, fields_list, context=None):
        if context is None:
            context = {}
        res = super(stock_invoice_onshipping, self).view_init(cr, uid, fields_list, context=context)
        pick_obj = self.pool.get('stock.picking')
        pick_out_obj = self.pool.get('stock.picking')
        count = 0
        active_ids = context.get('active_ids',[])
       # pick_out=None
        for pick in pick_obj.browse(cr, uid, active_ids, context=context):
#            if pick.type=='out':
#                pick_out = pick_out_obj.browse(cr, uid, pick.id)
            if pick.invoice_state != '2binvoiced' or pick.waybill_state!='none':
                    count += 1
        if len(active_ids) == 1 and count:
            raise osv.except_osv(_('Warning !'), _('This picking list does not require invoicing.'))
        if len(active_ids) == count:
            raise osv.except_osv(_('Warning !'), _('None of these picking lists require invoicing.'))
        return res
