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

from openerp.osv import osv, fields, orm
from openerp.tools.translate import _
from openerp import workflow


class account_pt_invoice_refund(osv.osv_memory):
    _name = "account.invoice.refund"
    _description = "Invoice Refund"
    _inherit = 'account.invoice.refund'

    def _get_description(self, cr, uid, context=None):
        if context is None:
            context = {}
        invoice_obj = self.pool.get('account.invoice')
        active_ids = context.get('active_ids', [])
        description = u''
        for invoice in invoice_obj.browse(cr, uid, active_ids):
            description += invoice.number
        return description

    _columns = {
        'force_open': fields.boolean(
            'Force Open',
            help="Select to force the opening of this document, "
                 "even if there are older drafts or created ones.\n"
                 "It doesn't force opening if there are higher ones."),
    }
    _defaults = {
        'description': _get_description,
    }

    TYPE_MAPPING = {
        'out_invoice': 'sale_refund',
        'out_refund': 'sale',
        'in_invoice': 'purchase_refund',
        'in_refund': 'purchase',
        'simplified_invoice': 'sale_refund',
        'debit_note': 'sale_refund',
        'in_debit_note': 'purchase_refund',
    }

    # TKO ACCOUNT PT: Inherit method
    def _get_journal(self, cr, uid, context=None):
        obj_journal = self.pool.get('account.journal')
        user_obj = self.pool.get('res.users')
        if context is None:
            context = {}
        inv_type = context.get('type', 'out_invoice')
        user = user_obj.browse(cr, uid, uid, context=context)
        company_id = user.company_id.id
        type = TYPE_MAPPING.get(inv_type, False)
        query = [('type', '=', type), ('company_id', '=', company_id)]
        journal = obj_journal.search(cr, uid, query, limit=1, context=context)
        return journal and journal[0] or False

    # TKO ACCOUNT PT: Inherit method
    def fields_view_get(self, cr, uid, view_id=None, view_type=False,
                        context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        user_obj = self.pool.get('res.users')
        res = super(account_pt_invoice_refund, self).fields_view_get(
            cr, uid, view_id=view_id, view_type=view_type, context=context,
            toolbar=toolbar, submenu=submenu)
        type = context.get('type', 'out_invoice')
        user = user_obj.browse(cr, uid, uid, context=context)
        company_id = user.company_id.id
        journal_type = TYPE_MAPPING.get(type, False)
        query = [('type', '=', journal_type),
                 ('company_id', 'child_of', [company_id])]
        journal_select = journal_obj._name_search(
            cr, uid, '', query, context=context)
        for field in res['fields']:
            if field == 'journal_id':
                res['fields'][field]['selection'] = journal_select
        return res

    # TKO ACCOUNT PT:Inherit method
    def compute_refund(self, cr, uid, ids, mode='refund', context=None):
        """
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: the account invoice refund’s ID or list of IDs
        """
        inv_obj = self.pool.get('account.invoice')
        reconcile_obj = self.pool.get('account.move.reconcile')
        account_m_line_obj = self.pool.get('account.move.line')
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        inv_tax_obj = self.pool.get('account.invoice.tax')
        inv_line_obj = self.pool.get('account.invoice.line')
        res_users_obj = self.pool.get('res.users')
        if context is None:
            context = {}

        for form in self.browse(cr, uid, ids, context=context):
            created_inv = []
            date = False
            period = False
            description = False
            user = res_users_obj.browse(cr, uid, uid, context=context)
            company = user.company_id
            journal_id = form.journal_id.id

            invoice_ids = context.get('active_ids', [])
            invoices = inv_obj.browse(cr, uid, invoice_ids, context=context)
            for inv in invoices:
                if inv.state in ('draft', 'proforma2', 'cancel'):
                    raise osv.except_osv(
                        _('Error!'),
                        _('Cannot %s draft/proforma/cancel invoice.') % (mode))
                if inv.reconciled and mode in ('cancel', 'modify'):
                    raise osv.except_osv(
                        _('Error!'),
                        _('Cannot %s invoice which is already reconciled, '
                          'invoice should be unreconciled first. You can only '
                          'refund this invoice.') % (mode))
                if form.period.id:
                    period = form.period.id
                elif inv.period_id:
                    period = inv.period_id
                else:
                    period = False
                # Resolve multi company
                if company.id != inv.company_id.id:
                    company = inv.company_id
                if not journal_id:
                    journal_id = inv.journal_id.id
                # Resolve multi company
                if form.journal_id.company_id.id != company.id:
                    raise osv.except_osv(
                        _('Error!'),
                        _('Company Journal is different of Invoice Company: '
                          'Company Invoice') % (inv.company_id.name))
                if form.date:
                    date = form.date
                    if not form.period.id:
                        fields_obj = self.pool['ir.model.fields']
                        query = [('model', '=', 'account.period'),
                                 ('name', '=', 'company_id')]
                        fields_ids = fields_obj.search(cr, uid, query)
                        if fields_ids:
                            query = 'select p.id from account_fiscalyear y, '\
                                    'account_period p '\
                                    'where y.id=p.fiscalyear_id '\
                                    'and date(%s) between p.date_start AND '\
                                    'p.date_stop and y.company_id = %s limit 1'
                            params = (date, company.id)
                        else:
                            query = 'SELECT id '\
                                    'from account_period where date(%s) '\
                                    'between date_start AND date_stop '\
                                    'limit 1'
                            params = (date,)
                        res = cr.fetchone()
                        if res:
                            period = res[0]
                else:
                    date = inv.date_invoice
                if form.description:
                    description = form.description
                else:
                    description = inv.name

                if not period:
                    raise osv.except_osv(
                        _('Insufficient Data!'),
                        _('No period found on the invoice.'))

                refund_id = inv_obj.refund(
                    cr, uid, [inv.id], date, period, description, journal_id,
                    context=context)
                refund = inv_obj.browse(cr, uid, refund_id[0], context=context)
                vals = {'date_due': date, 'check_total': inv.check_total}
                inv_obj.write(cr, uid, [refund.id], vals)
                inv_obj.button_compute(cr, uid, refund_id)

                created_inv.append(refund_id[0])
                if mode in ('cancel', 'modify'):
                    movelines = inv.move_id.line_id
                    to_reconcile_ids = {}
                    for line in movelines:
                        if line.account_id.id == inv.account_id.id:
                            to_reconcile_ids[line.account_id.id] = [line.id]
                        if type(line.reconcile_id) != orm.browse_null:
                            reconcile_obj.unlink(cr, uid, line.reconcile_id.id)
                    workflow.trg_validate(
                        uid, 'account.invoice', refund.id, 'invoice_open', cr)
                    refund = inv_obj.browse(
                        cr, uid, refund_id[0], context=context)
                    for tmpline in refund.move_id.line_id:
                        if tmpline.account_id.id == inv.account_id.id:
                            tmp_account_id = tmpline.account_id.id
                            to_reconcile_ids[tmp_account_id].append(tmpline.id)
                    for account in to_reconcile_ids:
                        account_m_line_obj.reconcile(
                            cr, uid, to_reconcile_ids[account],
                            writeoff_period_id=period,
                            writeoff_journal_id=inv.journal_id.id,
                            writeoff_acc_id=inv.account_id.id)
                    if mode == 'modify':
                        fields = [
                            'name', 'type', 'number', 'reference', 'comment',
                            'date_due', 'partner_id', 'partner_insite',
                            'partner_contact', 'partner_ref', 'payment_term',
                            'account_id', 'currency_id', 'invoice_line',
                            'tax_line', 'journal_id', 'period_id',
                        ]
                        invoice = inv_obj.read(
                            cr, uid, [inv.id], fields, context=context)[0]
                        del invoice['id']
                        invoice_lines = inv_line_obj.browse(
                            cr, uid, invoice['invoice_line'], context=context)
                        invoice_lines = inv_obj._refund_cleanup_lines(
                            cr, uid, invoice_lines)
                        tax_lines = inv_tax_obj.browse(
                            cr, uid, invoice['tax_line'], context=context)
                        tax_lines = inv_obj._refund_cleanup_lines(
                            cr, uid, tax_lines)
                        invoice.update({
                            'type': inv.type,
                            'date_invoice': date,
                            'state': 'draft',
                            'number': False,
                            'invoice_line': invoice_lines,
                            'tax_line': tax_lines,
                            'period_id': period,
                            'name': description
                        })
                        for field in ('partner_id', 'account_id',
                                      'currency_id', 'payment_term',
                                      'journal_id'):
                            if invoice[field]:
                                invoice[field] = invoice[field][0]
                            else:
                                invoice[field] = False
                        inv_id = inv_obj.create(cr, uid, invoice)
                        if inv.payment_term.id:
                            data = inv_obj.onchange_payment_term_date_invoice(
                                cr, uid, [inv_id], inv.payment_term.id, date)
                            if data.get('value'):
                                inv_obj.write(cr, uid, [inv_id], data['value'])
                        created_inv.append(inv_id)
            xml_id = self.get_action_window(cr, uid, inv.type)
            result = mod_obj.get_object_reference(cr, uid, 'account', xml_id)
            id = result and result[1] or False
            result = act_obj.read(cr, uid, id, context=context)
            invoice_domain = eval(result['domain'])
            invoice_domain.append(('id', 'in', created_inv))
            result['domain'] = invoice_domain
            return result

    def get_action_window(self, cr, uid, inv_type):
        """
        Get action window for documents
        """
        if not inv_type:
            return False
        return {
            'out_refund': 'action_invoice_tree1',
            'in_debit_note': 'action_invoice_tree2',
            'in_refund': 'action_invoice_tree2',
            'out_invoice': 'action_invoice_tree3',
            'simplified_invoice': 'action_invoice_tree3',
            'debit_note': 'action_invoice_tree3',
            'in_invoice': 'action_invoice_tree4'
        }.get(inv_type, False)
