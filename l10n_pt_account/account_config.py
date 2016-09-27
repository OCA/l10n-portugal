# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./
from openerp import models, fields, api


class ResCompany(models.Model):
    _inherit = "res.company"

    income_move_account_id = fields.Many2one(
        'account.account', string="Gain Account",
        help="Account to register the differences "
             "of values in invoices in gain (credit)")
    expense_move_account_id = fields.Many2one(
        'account.account', string="Loss Account",
        help="Account to register the differences "
             "of values in invoices in loss (debit)")


class AccountPtConfig(models.Model):
    _name = 'account.config.settings'
    _inherit = 'account.config.settings'

    debit_sup_seq_id = fields.Many2one(
        'ir.sequence', 'Supplier Debit Note Sequence')
    debit_sup_seq_prefix = fields.Char(
        'debit_sup_seq_id', 'prefix',
        string='Supplier debit note sequence')
    debit_sup_seq_next = fields.Integer(
        'debit_sup_seq_id', 'number_next',
        string='Supplier debit note next number')
    debit_journal_id = fields.Many2one(
        'account.journal', 'Debit Note journal')
    debit_seq_prefix = fields.Char(
        'debit_journal_id', 'sequence_id', 'prefix',
        string='Debit note sequence')
    waybill_rem_seq = fields.Many2one(
        'ir.sequence', 'Waybill Remittance Sequence')
    waybill_rem_seq_prefix = fields.Char(
        'waybill_rem_seq', 'prefix',
        string='Waybill remittance sequence')
    waybill_trsp_seq = fields.Many2one(
        'ir.sequence', 'Waybill Transport Sequence')
    waybill_trsp_seq_prefix = fields.Char(
        'waybill_trsp_seq', 'prefix',
        string='Waybill transport sequence')
    waybill_dev_seq = fields.Many2one(
        'ir.sequence', 'Waybill Return Sequence')
    waybill_dev_seq_prefix = fields.Char(
        'waybill_dev_seq', 'prefix',
        string='Waybill return sequence')
    module_tko_account_pt_partner_reports = fields.Boolean(
        'Allows to download partner PT reports.',
        help='Adds several reports. This installs the '
             'module tko_account_pt_partner_reports.')
    module_tko_account_pt_account_reports = fields.Boolean(
        'Overwrites accounting reports to add acumulated amounts.',
        help='Overwrites the Balance, General Ledger and adds '
             'a summary extracts report. This installs the '
             'module tko_account_pt_account_reports.')
    expense_move_account_id = fields.Many2one(
        'account.account', related='company_id.expense_move_account_id',
        string='Loss Differences Account',
        help="Account to register the differences of "
             "values in invoices in loss (debit)")
    income_move_account_id = fields.Many2one(
        'account.account', related='company_id.income_move_account_id',
        string='Gain Differences Account',
        help="Account to register the differences of "
             "values in invoices in gain (credit)")

    @api.model
    def get_default_fields(self, fields):
        res = {}
        journal_obj = self.env['account.journal']
        sequence_obj = self.env['ir.sequence']
        debit_note = journal_obj.search(
            [('code', '=', 'MISC'), ('type', '=', 'general')],
            limit=1)
        sup_debit_note = sequence_obj.search(
            [('code', '=', 'account.invoice.in_debit_note')], limit=1)
        waybill_rem = sequence_obj.search(
            [('code', '=', 'account.guia.remessa.sequence')], limit=1)
        waybill_trsp = sequence_obj.search(
            [('code', '=', 'account.guia.transporte.sequence')],
            limit=1)
        waybill_dev = sequence_obj.search(
            [('code', '=', 'account.guia.devolucao.sequence')],
            limit=1)
        if debit_note:
            res['debit_journal_id'] = debit_note.id
            res['debit_seq_prefix'] = debit_note.sequence_id.prefix
        if sup_debit_note:
            res['debit_sup_seq_id'] = sup_debit_note.id
            res['debit_sup_seq_prefix'] = sup_debit_note.prefix
            res['debit_sup_seq_next'] = sup_debit_note.number_next
        if waybill_rem:
            res['waybill_rem_seq'] = waybill_rem.id
            res['waybill_rem_seq_prefix'] = waybill_rem.prefix
        if waybill_trsp:
            res['waybill_trsp_seq'] = waybill_trsp.id
            res['waybill_trsp_seq_prefix'] = waybill_trsp.prefix
        if waybill_dev:
            res['waybill_dev_seq'] = waybill_dev.id
            res['waybill_dev_seq_prefix'] = waybill_dev.prefix
        return res

    @api.multi
    @api.onchange('company_id')
    def onchange_company_id(self):
        """ Update income/expense move account  """
        if self.company_id:
            if self.company_id.income_move_account_id:
                self.income_move_account_id = \
                    self.company_id.income_move_account_id.id
            if self.company_id.expense_move_account_id:
                self.expense_move_account_id = \
                    self.company_id.expense_move_account_id.id
