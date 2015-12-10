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

import time
from openerp.osv import fields, osv, orm
from openerp.tools.translate import _
from datetime import datetime

class account_pt_config(osv.osv_memory):
    _name = 'account.config.settings'
    _inherit = 'account.config.settings'

    _columns = {
                 'debit_sup_seq_id': fields.many2one('ir.sequence', 'Supplier Debit Note Sequence'),
                 'debit_sup_seq_prefix': fields.related('debit_sup_seq_id', 'prefix', type='char', string='Supplier debit note sequence'),
                 'debit_sup_seq_next': fields.related('debit_sup_seq_id', 'number_next', type='integer', string='Supplier debit note next number'),
                 'debit_journal_id': fields.many2one('account.journal', 'Debit Note journal'),
                 'debit_seq_prefix': fields.related('debit_journal_id', 'sequence_id', 'prefix', type='char', string='Debit note sequence'),
                 'waybill_rem_seq': fields.many2one('ir.sequence', 'Waybill Remittance Sequence'),
                 'waybill_rem_seq_prefix': fields.related('waybill_rem_seq', 'prefix', type='char', string='Waybill remittance sequence'),
                 'waybill_trsp_seq': fields.many2one('ir.sequence', 'Waybill Transport Sequence'),
                 'waybill_trsp_seq_prefix': fields.related('waybill_trsp_seq', 'prefix', type='char', string='Waybill transport sequence'),
                 'waybill_dev_seq': fields.many2one('ir.sequence', 'Waybill Return Sequence'),
                 'waybill_dev_seq_prefix': fields.related('waybill_dev_seq', 'prefix', type='char', string='Waybill return sequence'),
                 'module_tko_account_pt_stock_return': fields.boolean("Allow manage the stock returns", help='Adds options to return products. This installs the module tko_account_pt_stock_return.'),
                 'module_tko_account_pt_partner_reports': fields.boolean('Allows to download partner PT reports.', help='Adds several reports. This installs the module tko_account_pt_partner_reports.'),
                 'module_tko_account_pt_account_reports': fields.boolean('Overwrites accounting reports to add acumulated amounts.', help='Overwrites the Balance, General Ledger and adds a summary extracts report. This installs the module tko_account_pt_account_reports.'),
                }

    def get_default_fields(self, cr, uid, fields, context=None):
        if context is None: context = {}
        res={}
        journal_obj = self.pool.get('account.journal')
        sequence_obj = self.pool.get('ir.sequence')
        debit_note_id = journal_obj.search(cr, uid, [('code', '=', 'MISC'), ('type', '=', 'general')], limit=1)
        sup_debit_note = sequence_obj.search(cr, uid, [('code', '=', 'account.invoice.in_debit_note')], limit=1)
        waybill_rem = sequence_obj.search(cr, uid, [('code', '=', 'account.guia.remessa.sequence')], limit=1)
        waybill_trsp = sequence_obj.search(cr, uid, [('code', '=', 'account.guia.transporte.sequence')], limit=1)
        waybill_dev = sequence_obj.search(cr, uid, [('code', '=', 'account.guia.devolucao.sequence')], limit=1)
        if debit_note_id:
            debit_note = journal_obj.browse(cr, uid, debit_note_id[0])
            res['debit_journal_id']= debit_note.id
            res['debit_seq_prefix']= debit_note.sequence_id.prefix
        if sup_debit_note:
            sup_d_note = sequence_obj.browse(cr, uid, sup_debit_note[0])
            res['debit_sup_seq_id']= sup_d_note.id
            res['debit_sup_seq_prefix']=sup_d_note.prefix
            res['debit_sup_seq_next'] = sup_d_note.number_next
        if waybill_rem:
            seq_rem = sequence_obj.browse(cr, uid, waybill_rem[0])
            res['waybill_rem_seq']= seq_rem.id
            res['waybill_rem_seq_prefix']= seq_rem.prefix
        if waybill_trsp:
            seq_trsp = sequence_obj.browse(cr, uid, waybill_trsp[0])
            res['waybill_trsp_seq']= seq_trsp.id
            res['waybill_trsp_seq_prefix']= seq_trsp.prefix
        if waybill_dev:
            seq_dev = sequence_obj.browse(cr, uid, waybill_dev[0])
            res['waybill_dev_seq']= seq_dev.id
            res['waybill_dev_seq_prefix']= seq_dev.prefix
        return res
