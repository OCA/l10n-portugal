# -*- coding: utf-8 -*-
from openerp.osv import fields, osv, orm
from openerp.tools.translate import _
from datetime import datetime

class res_company(osv.osv):
    _inherit="res.company"
    
    _columns = {
                'income_move_account_id': fields.many2one('account.account',"Gain Account", help="Account to register the differences of values in invoices in gain (credit)"),
                'expense_move_account_id': fields.many2one('account.account',"Loss Account", help="Account to register the differences of values in invoices in loss (debit)",),
                }

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
                 'module_tko_account_pt_partner_reports': fields.boolean('Allows to download partner PT reports.', help='Adds several reports. This installs the module tko_account_pt_partner_reports.'),
                 'module_tko_account_pt_account_reports': fields.boolean('Overwrites accounting reports to add acumulated amounts.', help='Overwrites the Balance, General Ledger and adds a summary extracts report. This installs the module tko_account_pt_account_reports.'),
                 'expense_move_account_id': fields.many2one('account.account', related='company_id.expense_move_account_id', string='Loss Differences Account', help="Account to register the differences of values in invoices in loss (debit)"),
                 'income_move_account_id': fields.many2one('account.account', related='company_id.income_move_account_id', string='Gain Differences Account', help="Account to register the differences of values in invoices in gain (credit)"),
                }

    def get_default_fields(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = {}
        journal_obj = self.pool.get('account.journal')
        sequence_obj = self.pool.get('ir.sequence')
        debit_note_id = journal_obj.search(
            cr, uid, [('code', '=', 'MISC'), ('type', '=', 'general')],
            limit=1)
        sup_debit_note = sequence_obj.search(
            cr, uid, [('code', '=', 'account.invoice.in_debit_note')], limit=1)
        waybill_rem = sequence_obj.search(
            cr, uid, [('code', '=', 'account.guia.remessa.sequence')], limit=1)
        waybill_trsp = sequence_obj.search(
            cr, uid, [('code', '=', 'account.guia.transporte.sequence')],
            limit=1)
        waybill_dev = sequence_obj.search(
            cr, uid, [('code', '=', 'account.guia.devolucao.sequence')],
            limit=1)
        if debit_note_id:
            debit_note = journal_obj.browse(cr, uid, debit_note_id[0])
            res['debit_journal_id'] = debit_note.id
            res['debit_seq_prefix'] = debit_note.sequence_id.prefix
        if sup_debit_note:
            sup_d_note = sequence_obj.browse(cr, uid, sup_debit_note[0])
            res['debit_sup_seq_id'] = sup_d_note.id
            res['debit_sup_seq_prefix'] = sup_d_note.prefix
            res['debit_sup_seq_next'] = sup_d_note.number_next
        if waybill_rem:
            seq_rem = sequence_obj.browse(cr, uid, waybill_rem[0])
            res['waybill_rem_seq'] = seq_rem.id
            res['waybill_rem_seq_prefix'] = seq_rem.prefix
        if waybill_trsp:
            seq_trsp = sequence_obj.browse(cr, uid, waybill_trsp[0])
            res['waybill_trsp_seq'] = seq_trsp.id
            res['waybill_trsp_seq_prefix'] = seq_trsp.prefix
        if waybill_dev:
            seq_dev = sequence_obj.browse(cr, uid, waybill_dev[0])
            res['waybill_dev_seq'] = seq_dev.id
            res['waybill_dev_seq_prefix'] = seq_dev.prefix
        return res
    
    def onchange_company_id(self, cr, uid, ids, company_id, context=None):
        """ Update income/expense move account  """

        values = super(account_pt_config, self).onchange_company_id(cr, uid, ids, company_id, context=None)
        
        if company_id:
            company = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
            values.update({
                'income_move_account_id': company.income_move_account_id and company.income_move_account_id.id or False,
                'expense_move_account_id': company.expense_move_account_id and company.expense_move_account_id.id or False
            })

        return {'value': values}
            
