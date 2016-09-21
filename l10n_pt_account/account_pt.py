# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./

from openerp import api, models, fields, _
from openerp.exceptions import Warning


class AccountTax(models.Model):
    _inherit = 'account.tax'

    # Adding field to map account in debit notes
    account_debit_id = fields.Many2one('account.account',
                                       string='Debit Tax Account')

    # TKO ACCOUNT PT: Inherit method
    # Map field account_debit_id
    # TODO: identify if this is still needed
    @api.model
    def _unit_compute(self, taxes, price_unit,
                      product=None, partner=None, quantity=0):
        data = super(AccountTax, self)._unit_compute(
            taxes, price_unit, product, partner, quantity)
        for dict in data:
            if 'id' in dict:
                account_debit_id = self.browse(dict['id'])
                if account_debit_id:
                    dict.update({'account_debit_id': account_debit_id.id})
        return data

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        context = self._context or {}

        if context.get('type'):
            if context.get('type') == 'simplified_invoice':
                args += [('type_tax_use', 'in', ['sale', 'all'])]
            elif context.get('type') == 'in_debit_note':
                args += [('type_tax_use', 'in', ['purchase', 'all'])]
        return super(AccountTax, self).search(
            args, offset, limit, order, count=count)

    # TKO ACCOUNT PT: Inherit method
    # Map field account_debit_id
    # TODO: identify if this is still needed
    @api.model
    def _unit_compute_inv(self, taxes, price_unit, product=None, partner=None):
        data = super(AccountTax, self)._unit_compute_inv(
            taxes, price_unit, product, partner)
        for dict in data:
            account_debit_id = self.browse(dict['id'])
            if account_debit_id:
                dict.update({'account_debit_id': account_debit_id.id})
        return data


class AccountMove(models.Model):
    _inherit = 'account.move'

    # TKO ACCOUNT PT: Inherit method
    # To write in_debit_note sequence
    @api.multi
    def post(self):
        invoice = self._context.get('invoice', False)
        self._post_validate()

        for move in self:
            move.line_ids.create_analytic_lines()
            if move.name == '/':
                new_name = False
                journal = move.journal_id

                if invoice and invoice.move_name and invoice.move_name != '/':
                    new_name = invoice.move_name
                elif invoice and invoice.type == 'in_debit_note':
                    debit_seq = 'account.invoice.in_debit_note'
                    new_name = self.env['ir.sequence'].next_by_code(debit_seq)
                elif invoice and journal.sequence_id:
                    # If invoice is actually refund and journal has a
                    # refund_sequence then use that one or use the
                    # regular one
                    sequence = journal.sequence_id
                    is_refund = invoice.type in ('out_refund', 'in_refund')
                    if is_refund and journal.refund_sequence:
                        sequence = journal.refund_sequence_id
                    new_name = sequence\
                        .with_context(ir_sequence_date=move.date)\
                        .next_by_id()
                else:
                    raise Warning(_('Please define a sequence '
                                    'on the journal.'))

                if new_name:
                    move.name = new_name
        return self.write({'state': 'posted'})


class AccountJournal(models.Model):
    _inherit = "account.journal"

    stock_journal = fields.Boolean(string='Stock Journal')

    # TKO ACCOUNT PT: method to write only one stock journal
    @api.multi
    def _check_unique_stock_journal(self):
        company_ids = [line.company_id.id for line in self]
        companies_found = self.env['res.company'].browse()
        query = [
            ('company_id', 'in', company_ids),
            ('stock_journal', '=', True),
        ]
        stock_journals = self.search(query)
        for journal in stock_journals:
            if journal.company_id not in companies_found:
                companies_found |= journal.company_id
            else:
                return False
        return True

    _constraints = [
        (_check_unique_stock_journal,
         'Only one journal can be selected as stock journal!',
         ['stock_journal']),
    ]
