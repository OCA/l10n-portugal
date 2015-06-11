# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 Thinkopen Solutions, Lda. All Rights Reserved
#    http://www.thinkopensolutions.com.
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
from openerp.tools.translate import _


class account_pt_account_tax(osv.osv):
    _name = "account.tax"
    _description = "Invoice Tax"
    _inherit = 'account.tax'

    # Adding field to map account in debit notes
    _columns = {'account_debit_id': fields.many2one(
        'account.account', 'Debit Tax Account')}

    # TKO ACCOUNT PT: Inherit method
    # Map field account_debit_id
    def _unit_compute(self, cr, uid, taxes, price_unit, product=None,
                      partner=None, quantity=0):
        data = super(account_pt_account_tax, self)._unit_compute(
            cr, uid, taxes, price_unit, product, partner, quantity)
        for dict in data:
            if 'id' in dict:
                account_debit_id = self.browse(cr, uid, dict['id'])
                if account_debit_id:
                    dict.update({'account_debit_id': account_debit_id.id})
        return data

    def search(self, cr, uid, args, offset=0, limit=None, order=None,
               context=None, count=False):
        if context is None:
            context = {}

        if context.get('type'):
            if context.get('type') == 'simplified_invoice':
                args += [('type_tax_use', 'in', ['sale', 'all'])]
            elif context.get('type') == 'in_debit_note':
                args += [('type_tax_use', 'in', ['purchase', 'all'])]
        return super(account_pt_account_tax, self).search(
            cr, uid, args, offset=offset, limit=limit, order=order,
            context=context, count=count)

    # TKO ACCOUNT PT: Inherit method
    # Map field account_debit_id
    def _unit_compute_inv(self, cr, uid, taxes, price_unit, product=None,
                          partner=None):
        data = super(account_pt_account_tax, self). _unit_compute_inv(
            cr, uid, taxes, price_unit, product, partner)
        for dict in data:
            account_debit_id = self.browse(cr, uid, dict['id'])
            if account_debit_id:
                dict.update({'account_debit_id': account_debit_id.id, })
        return data


class account_pt_move(osv.osv):
    _name = "account.move"
    _inherit = 'account.move'

    # TKO ACCOUNT PT: Inherit method
    # To write in_debit_note sequence
    def post(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        invoice = context.get('invoice', False)
        valid_moves = self.validate(cr, uid, ids, context)

        if not valid_moves:
            raise osv.except_osv(
                _('Error!'),
                _('You cannot validate a non-balanced entry.\n'
                  'Make sure you have configured payment terms properly.\n'
                  'The latest payment term line should be of the "Balance" '
                  'type.'))
        obj_sequence = self.pool.get('ir.sequence')
        for move in self.browse(cr, uid, valid_moves, context=context):
            if move.name == '/':
                new_name = False
                journal = move.journal_id

                invoice_internal_number = invoice and invoice.internal_number
                invoice_type = invoice and invoice.type
                if invoice_internal_number:
                    new_name = invoice_internal_number
                elif invoice_type == 'in_debit_note':
                    new_name = obj_sequence.get(
                        cr, uid, 'account.invoice.in_debit_note')
                else:
                    if journal.sequence_id:
                        c = {'fiscalyear_id': move.period_id.fiscalyear_id.id}
                        new_name = obj_sequence.next_by_id(
                            cr, uid, journal.sequence_id.id, c)
                    else:
                        raise osv.except_osv(
                            _('Error!'),
                            _('Please define a sequence on the journal.'))

                if new_name:
                    self.write(cr, uid, [move.id], {'name': new_name})

        cr.execute('UPDATE account_move '
                   'SET state=%s '
                   'WHERE id IN %s',
                   ('posted', tuple(valid_moves),))
        return True


class account_journal(osv.osv):
    _inherit = "account.journal"

    _columns = {
        'stock_journal': fields.boolean("Stock Journal"),
    }
    # TKO ACCOUNT PT: method to write only one stock journal

    def _check_unique_stock_journal(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context=context):
            query = [('company_id', '=', line.company_id.id),
                     ('stock_journal', '=', True)]
            stock_journal_count = self.search(cr, uid, query)
            if len(stock_journal_count) > 1:
                return False
        return True

    _constraints = [
        (_check_unique_stock_journal,
         'Only one journal can be selected as stock journal!',
         ['stock_journal']),
    ]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
