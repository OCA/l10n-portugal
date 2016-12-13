# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from openerp import models, fields, api, _


class StockInvoiceOnshipping(models.TransientModel):
    _name = "stock.invoice.onshipping"
    _inherit = "stock.invoice.onshipping"

    @api.model
    def view_init(self, fields_list):
        res = super(StockInvoiceOnshipping, self).view_init(
            fields_list)
        pick_obj = self.env['stock.picking']
        count = 0
        active_ids = self._context.get('active_ids', [])
        for pick in pick_obj.browse(active_ids):
            if pick.invoice_state != '2binvoiced'\
               or pick.waybill_state != 'none':
                count += 1
        if len(active_ids) == 1 and count:
            raise Warning( 
                _('This picking list does not require invoicing or '
                  'already created a waybill.'))
        if len(active_ids) == count:
            raise Warning( 
                _('None of these picking lists require invoicing or '
                  'already created a waybill.'))
        return res
