# -*- coding: utf-8 -*-
from openerp.osv import fields, osv, orm
from openerp.tools.translate import _
from datetime import datetime

import time


class account_pt_config(osv.osv_memory):
    _name = 'account.config.settings'
    _inherit = 'account.config.settings'

    module_tko_account_pt_account_reports = fields.Boolean(
        'Overwrites accounting reports to add acumulated amounts.',
        help=('Overwrites the Balance, General Ledger and adds a summary '
              'extracts report. This installs the module '
              'tko_account_pt_account_reports.'))
    module_tko_account_pt_partner_reports = fields.Boolean(
        'Allows to download partner PT reports.',
        help=('Adds several reports. This installs the module '
              'tko_account_pt_partner_reports.'))
    module_tko_account_pt_stock_return = fields.Boolean(
        "Allow manage the stock returns",
        help=('Adds options to return products. This installs the module '
              'tko_account_pt_stock_return.'))
    waybill_dev_seq_prefix = fields.Char(
        string='Waybill return sequence', related='waybill_dev_seq.prefix')
    waybill_dev_seq = fields.Many2one('ir.sequence', 'Waybill Return Sequence')
    waybill_trsp_seq_prefix = fields.Char(
        string='Waybill transport sequence', related='waybill_trsp_seq.prefix')
    waybill_trsp_seq = fields.Many2one(
        'ir.sequence', 'Waybill Transport Sequence')
    waybill_rem_seq_prefix = fields.Char(
        string='Waybill remittance sequence',
        related='waybill_rem_seq.prefix')
    waybill_rem_seq = fields.Many2one(
        'ir.sequence', 'Waybill Remittance Sequence')
    debit_seq_prefix = fields.Char(
        string='Debit note sequence',
        related='debit_journal_id.sequence_id.prefix')
    debit_journal_id = fields.Many2one('account.journal', 'Debit Note journal')
    debit_sup_seq_next = fields.Integer(
        string='Supplier debit note next number',
        related='debit_sup_seq_id.number_next')
    debit_sup_seq_prefix = fields.Char(
        string='Supplier debit note sequence',
        related='debit_sup_seq_id.prefix')
    debit_sup_seq_id = fields.Many2one(
        'ir.sequence', 'Supplier Debit Note Sequence')

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
