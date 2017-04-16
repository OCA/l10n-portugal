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
from openerp import fields as new_fields, SUPERUSER_ID
from openerp.tools.translate import _
from openerp import api

from itertools import groupby
from datetime import datetime
import time

EXEMPTION_REASONS = enumerate([
    u'Artigo 16.º n.º 6 alínea c) do CIVA',
    u'Artigo 6.º do Decreto‐Lei n.º 198/90, de 19 de Junho',
    u'Exigibilidade de caixa',
    u'Isento Artigo 13.º do CIVA',
    u'Isento Artigo 14.º do CIVA',
    u'Isento Artigo 15.º do CIVA',
    u'Isento Artigo 9.º do CIVA',
    u'IVA – Autoliquidação',
    u'IVA ‐ não confere direito a dedução',
    u'IVA – Regime de isenção',
    u'Não tributado',
    u'Regime da margem de lucro- Agências de Viagens',
    u'Regime da margem de lucro- Bens em segunda mão',
    u'Regime da margem de lucro- Objetos de arte',
    u'Regime da margem de lucro- Objetos de coleção e antiguidades',
    u'Isento Artigo 14.º do RITI',
])
EXEMPTION_SELECTION = [(str(i), t) for (i, t) in EXEMPTION_REASONS]


class one2many_mod2(fields.one2many):
    """
        Overwrite one2many field to get only note lines
    """

    def get(self, cr, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        if not values:
            values = {}
        res = {}
        for id in ids:
            res[id] = []
        query = [(self._fields_id, 'in', ids), ('product_id', '!=', False)]
        obj_pool = obj.pool.get(self._obj)
        ids2 = obj_pool.search(cr, user, query, limit=self._limit)
        for r in obj_pool.read(cr, user, ids2, [self._fields_id],
                               context=context, load='_classic_write'):
            res[r[self._fields_id]].append(r['id'])
        return res


class account_pt_invoice(osv.osv):
    _name = "account.invoice"
    _description = 'Invoice'
    _inherit = 'account.invoice'
    _order = "date_invoice desc, number desc"

    def _check_state(state):  # not a method, just a help function
        def _(self, cr, uid, obj, context=None):
            out_states = ('out_invoice', 'out_refund',
                          'simplified_invoice', 'debit_note')
            return (obj['type'] in out_states) and (obj['state'] == state)
        return _

    _track = {
        'type': {
        },
        'state': {
            'account.mt_invoice_paid': _check_state('paid'),
            'account.mt_invoice_validated': _check_state('open'),
            'tko_account_pt.mt_invoice_canceled': _check_state('cancel'),
        },
    }

    def _convert_ref(self, ref):
        return (ref or '').replace('/', '')

    def _check_selection_field_value(self, cr, uid, field, value,
                                     context=None):
        if field == 'type' and \
           value in ('debit_note', 'in_debit_note', 'simplified_invoice'):
            return
        super(account_pt_invoice, self)._check_selection_field_value(
            cr, uid, field, value, context=context)

    # TKO ACCOUNT PT: New method
    def _today(*a):
        return datetime.now().strftime("%Y-%m-%d")

    # TKO ACCOUNT PT: Inherit method
    # To clean fields of reference documents from invoice_lines when create
    # refund
    def _refund_cleanup_lines(self, cr, uid, lines, context=None):
        lines = super(account_pt_invoice, self)._refund_cleanup_lines(
            cr, uid, lines, context=context)
        for x, y, line in lines:
            if 'waybill_reference' in line:
                line['waybill_reference'] = False
            if 'waybill_date' in line:
                line['waybill_date'] = False
        return lines

    # TKO ACCOUNT PT: New method that changes accounts from fiscal position
    def button_change_fiscal_position(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        fpos_obj = self.pool.get('account.fiscal.position')
        inv_line_obj = self.pool.get('account.invoice.line')

        inv = self.browse(cr, uid, ids)[0]
        for line in inv.invoice_line:
            account_line = fpos_obj.map_account(
                cr, uid, inv.fiscal_position, line.account_id.id)
            out_types = ('out_invoice', 'debit_note',
                         'simplified_invoice', 'out_refund')
            if inv.type in out_types:
                taxes = line.product_id.taxes_id
            else:
                taxes = line.product_id.supplier_taxes_id
            new_taxes = fpos_obj.map_tax(cr, uid, inv.fiscal_position, taxes)
            vals = {'account_id': account_line,
                    'invoice_line_tax_id': [(6, 0, new_taxes)]}
            inv_line_obj.write(cr, uid, [line.id], vals, context=context)
        account_inv = fpos_obj.map_account(
            cr, uid, inv.fiscal_position, inv.account_id.id)
        self.write(cr, uid, [inv.id], {'account_id': account_inv},
                   context=context)
        return True

    # TKO ACCOUNT PT: New method that gets payment term to simplified invoices
    def _get_payment_term(self, cr, uid, context=None):
        if context.get('type') == 'simplified':
            term_obj = self.pool.get('account.payment.term')
            query = [('name', '=', 'Pronto Pagamento')]
            return term_obj.search(cr, uid, query)[0]

    type = new_fields.Selection(selection_add=[
        ('debit_note', 'Debit Note'),
        ('in_debit_note', 'Supplier Debit Note'),
        ('simplified_invoice', 'Simplified Invoice')])

    edit_drafts = {'draft': [('readonly', False)]}

    _columns = {
        'fiscal_position': fields.many2one(
            'account.fiscal.position', 'Fiscal Position', readonly=True,
            states=edit_drafts),
        'waybill_ids': fields.one2many(
            'account.guia', 'invoice_id', 'Waybills'),
        'with_transport_info': fields.boolean(
            'Transport Information?', readonly=True, states=edit_drafts),
        'load_date': fields.datetime(
            'Load date', readonly=True, states=edit_drafts),
        'unload_date': fields.datetime(
            'Unload date', readonly=True, states=edit_drafts),
        'load_place': fields.char(
            'Load place', size=256, readonly=True, states=edit_drafts),
        'unload_place': fields.char(
            'Unload place', size=256, readonly=True, states=edit_drafts),
        'load_city': fields.char(
            'Load city', size=256, readonly=True, states=edit_drafts),
        'unload_city': fields.char(
            'Unload city', size=256, readonly=True, states=edit_drafts),
        'load_postal_code': fields.char(
            'Load postal_code', size=256, readonly=True, states=edit_drafts),
        'unload_postal_code': fields.char(
            'Unload postal_code', size=256, readonly=True, states=edit_drafts),
        'car_registration': fields.many2one(
            "account.license_plate", string="License Plate", readonly=True,
            states=edit_drafts),
        'exemption_reason': fields.selection(
            EXEMPTION_SELECTION, 'Exemption Reason', readonly=True,
            states=edit_drafts),
        'waybill_ref': fields.char(
            'Reference',
            help="To reference invoice lines you must write waybill number.",
            readonly=True, states=edit_drafts),
        'abstract_line_ids': fields.one2many(
            'account.invoice.line', 'invoice_id', 'Invoice Lines',
            readonly=True, copy=True, states=edit_drafts),
        'invoice_line': one2many_mod2(
            'account.invoice.line', 'invoice_id', 'Invoice Lines',
            readonly=True, copy=True, states=edit_drafts),
    }

    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'with_transport_info': False,
            'waybill_ref': False,
            'waybill_ids': False,
            'date_invoice': self._today(),
            'invoice_line': False,
        })
        return super(account_pt_invoice, self).copy(cr, uid, id, default,
                                                    context)

    # TKO ACCOUNT PT: New method
    def _get_client_if_simplified(self, cr, uid, context=None):
        if context and context.get('type') == 'simplified_invoice':
            # to get a database ID from an XML ID
            pool = self.pool.get('ir.model.data')
            client_id = pool.get_object(
                cr, uid, 'tko_account_pt', 'simplified_invoice_client')
            return client_id.id

    # TKO ACCOUNT PT: New method
    def _get_address_if_simplified(self, cr, uid, context=None):
        if context and context.get('type') == 'simplified_invoice':
            # to get a database ID from an XML ID
            pool = self.pool.get('ir.model.data')
            address_id = pool.get_object(
                cr, uid, 'tko_account_pt', 'simplified_invoice_client_address')
            return address_id.id

    # TKO ACCOUNT PT: New method
    def _get_account_if_simplified(self, cr, uid, context=None):
        client_id = self._get_client_if_simplified(cr, uid, context)
        if client_id:
            client_obj = self.pool.get('res.partner')
            [client] = client_obj.browse(cr, uid, [client_id], context=context)
            return client.property_account_receivable.id

    # TKO ACCOUNT PT: New method
    def _max_amount_simplified_invoices(self, cr, uid, ids):
        is_simplified = lambda invoice: invoice.type == 'simplified_invoice'
        for invoice in self.browse(cr, uid, ids):
            if is_simplified(invoice) and invoice.amount_untaxed > 1000:
                return False
        return True

    _defaults = {
        'payment_term': _get_payment_term,
        'partner_id': _get_client_if_simplified,
        'date_invoice': _today,
        'account_id': _get_account_if_simplified,
        'load_place': "N/ Armazém",
        'unload_place': "Morada Cliente",
        'load_date': lambda *a: datetime.now().strftime("%Y-%m-%d %H:%M:00"),
        'unload_date': lambda *a: datetime.now().strftime("%Y-%m-%d 22:59:59"),
    }

    _constraints = [
        (_max_amount_simplified_invoices,
         "The Simplified Invoices can only have a total up to 1000€",
         ['amount_total', 'state']),
    ]

    # TKO ACCOUNT PT: Inherit method
    def invoice_validate(self, cr, uid, ids, context=None):
        """
        Overwrites invoice_validate from account to reference
        invoice lines with waybill.
        """
        invoice_lines_obj = self.pool.get('account.invoice.line')
        waybill_obj = self.pool.get('account.guia')
        dict = {}
        result = super(account_pt_invoice, self).invoice_validate(
            cr, uid, ids, context)
        for inv in self.browse(cr, uid, ids):
            if inv.type == 'simplified_invoice' and inv.amount_total > 1000.0:
                raise osv.except_osv(
                    _('Error!'),
                    _('You can\'t create simplified invoices with '
                      'a total over 1000€'))
            if inv.type in ('out_invoice', 'simplified_invoice'):
                count = 0
                for line in inv.invoice_line:
                    if line.waybill_reference:
                        count += 1
                if count <= 0 and inv.waybill_ref:
                    lines = map(lambda x: x.id, inv.invoice_line)
                    query = [('numero', '=', inv.waybill_ref)]
                    waybill_ids = waybill_obj.search(cr, uid, query)
                    if waybill_ids:
                        [waybill_id] = waybill_ids
                        waybill = waybill_obj.browse(cr, uid, waybill_id)
                        dict = {
                            'waybill_reference': waybill.numero,
                            'waybill_date': waybill.data_carga.split()[0]
                        }
                        invoice_lines_obj.write(cr, uid, lines, dict)
                    else:
                        raise osv.except_osv(
                            _('Error!'),
                            _('Waybill Reference not found: %s' %
                              inv.waybill_ref))
        return result

    # TKO ACCOUNT PT:Inherit method

    def get_transport_fields(self, cr, uid, partner_id):
        partner_pool = self.pool.get('res.partner')
        address_id = partner_pool.address_get(
            cr, uid, [partner_id], ['delivery'])['delivery']
        if not address_id:
            values = {}
        [address] = partner_pool.browse(cr, uid, [address_id])
        values = {'unload_city': address.city if address.city else '',
                  'unload_postal_code': address.zip if address.zip else ''}
        return values

    def onchange_partner_id(self, cr, uid, ids, type, partner_id,
                            date_invoice=False, payment_term=False,
                            partner_bank_id=False, company_id=False,
                            context=None):
        if type in ('debit_note', 'simplified_invoice'):
            type = 'out_invoice'
        parent_dict = super(account_pt_invoice, self).onchange_partner_id(
            cr, uid, ids, type, partner_id, date_invoice, payment_term,
            partner_bank_id, company_id, context=context)
        if partner_id:
            transport_fields = self.get_transport_fields(cr, uid, partner_id)
            parent_dict['value'].update(transport_fields)
        return parent_dict

    def _update_lines_account(self, cr, uid, ids, company_id):
        account_obj = self.pool.get('account.account')
        inv_line_obj = self.pool.get('account.invoice.line')
        for invoice in self.browse(cr, uid, ids):
            get_account_name = lambda line: line.account_id.id
            sorted_lines = sorted(invoice.invoice_line, key=get_account_name)
            grouped_lines = dict(groupby(sorted_lines, get_account_name))
            original_accounts_names = grouped_lines.keys()
            query = [('name', 'in', original_accounts_names),
                     ('company_id', '=', company_id)]
            resp_accounts_ids = account_obj.search(cr, uid, query)
            if len(original_accounts_names) < len(resp_accounts_ids):
                msg = _(r'Cannot find a chart of account, you should create '
                        r'one from Settings\Configuration\Accounting menu.')
                raise osv.except_osv(_('Configuration Error!'), msg)
            resp_accounts = account_obj.browse(cr, uid, resp_accounts_ids)
            for account in resp_accounts:
                matching_lines = grouped_lines.get(account.name)
                lines_ids = [line.id for line in matching_lines]
                vals = {'account_id': account.id}
                inv_line_obj.write(cr, uid, lines_ids, vals)

    def onchange_company_id(self, cr, uid, ids, company_id, part_id, type,
                            invoice_line, currency_id, context=None):
        val = {}
        dom = {}
        obj_journal = self.pool.get('account.journal')
        account_obj = self.pool.get('account.account')
        partner_obj = self.pool.get('res.partner')
        if company_id and part_id and type:
            acc_id = False
            partner_obj = partner_obj.browse(cr, uid, part_id, context=context)
            if partner_obj.property_account_payable and \
               partner_obj.property_account_receivable:
                payable_acc = partner_obj.property_account_payable
                receivable_acc = partner_obj.property_account_receivable
                if payable_acc.company_id.id != company_id and \
                   receivable_acc.company_id.id != company_id:
                    prop_obj = self.pool.get('ir.property')
                    company_ctx = dict(context, force_company=company_id)
                    rec_field = 'property_account_receivable'
                    rec = prop_obj.get(cr, uid, rec_field, 'res.partner',
                                       part_id, context=company_ctx)
                    if not rec:
                        rec = prop_obj.get(cr, uid, rec_field, 'res.partner',
                                           context=company_ctx)
                    pay_field = 'property_account_payable'
                    pay = prop_obj.get(cr, uid, pay_field, 'res.partner',
                                       part_id, context=company_ctx)
                    if not rec:
                        pay = prop_obj.get(cr, uid, pay_field, 'res.partner',
                                           context=company_ctx)
                    if not rec and not pay:
                        error_msg = _(
                            'Cannot find a chart of account, you '
                            'should create one from '
                            'Settings\Configuration\Accounting menu.')
                        raise osv.except_osv(
                            _('Configuration Error!'),
                            error_msg)

                    if type in ('out_invoice', 'debit_note',
                                'simplified_invoice', 'out_refund'):
                        acc_id = rec.id if rec else False
                    else:
                        acc_id = pay.id if pay else False
                    val = {'account_id': acc_id}
            if ids:
                if company_id:
                    self._update_lines_account(cr, uid, ids, company_id)
            elif invoice_line:
                account_ids = [line[2]['account_id']
                               for line in invoice_line
                               if line[0] != 6]
                deduplicated_ids = list(set(account_ids))
                accounts = account_obj.browse(cr, uid, deduplicated_ids)
                if any(acc.company_id.id != company_id for acc in accounts):
                    msg = _('Invoice line account\'s company and '
                            'invoice\'s company does not match.')
                    raise osv.except_osv(_('Configuration Error!'), msg)

        if company_id and type:
            if type in ('out_invoice', 'simplified_invoice'):
                journal_type = 'sale'
            elif type in ('out_refund'):
                journal_type = 'sale_refund'
            elif type in ('in_refund'):
                journal_type = 'purchase_refund'
            elif type in ('debit_note', 'in_debit_note'):
                journal_type = 'general'
            else:
                journal_type = 'purchase'
            query = [('company_id', '=', company_id),
                     ('type', '=', journal_type)]
            journal_ids = obj_journal.search(cr, uid, query)
            if journal_ids:
                val['journal_id'] = journal_ids[0]
            ir_values_obj = self.pool.get('ir.values')
            res_journal_default = ir_values_obj.get(
                cr, uid, 'default', 'type=%s' % (type), ['account.invoice'])
            for r in res_journal_default:
                if r[1] == 'journal_id' and r[2] in journal_ids:
                    val['journal_id'] = r[2]
            if not val.get('journal_id', False):
                msg = _('Cannot find any account journal of %s type for this '
                        'company.\n\nYou can create one in the menu: '
                        '\nConfiguration\Journals\Journals.') % journal_type
                raise osv.except_osv(_('Configuration Error!'), msg)
            dom = {'journal_id':  [('id', 'in', journal_ids)]}
        else:
            journal_ids = obj_journal.search(cr, uid, [])

        return {'value': val, 'domain': dom}

    @api.multi
    def _get_analytic_lines(self):
        lines = super(account_pt_invoice, self)._get_analytic_lines()
        if self.type in ('debit_note', 'simplified_invoice'):
            for line in lines:
                if 'amount' in line:
                    line['amount'] *= -1
        return lines

    @api.multi
    def compute_invoice_totals(self, company_currency, ref,
                               invoice_move_lines):
        total = 0
        total_currency = 0
        for line in invoice_move_lines:
            if self.currency_id != company_currency:
                currency = self.currency_id.with_context(
                    date=self.date_invoice or fields.Date.today())
                line['currency_id'] = currency.id
                line['amount_currency'] = line['price']
                line['price'] = currency.compute(
                    line['price'], company_currency)
            else:
                line['currency_id'] = False
                line['amount_currency'] = False
            line['ref'] = ref
            valid_types = ('out_invoice', 'in_refund',
                           'debit_note', 'simplified_invoice')
            if self.type in valid_types:
                total += line['price']
                total_currency += line['amount_currency'] or line['price']
                line['price'] = -line['price']
            else:
                total -= line['price']
                total_currency -= line['amount_currency'] or line['price']
        return total, total_currency, invoice_move_lines

    def set_waybills_as_invoiced(self, obj_inv):
        # here we need to gain permissions, since the user might not be the in
        # waybill group
        obj_inv = obj_inv.with_env(self.env(user=SUPERUSER_ID))
        if obj_inv.waybill_ids:
            obj_inv.waybill_ids.write({'invoice_state': 'invoiced'})

    # TKO ACCOUNT PT:Inherit method
    @api.multi
    def action_number(self):
        # TODO: not correct fix but required a frech values before reading it.
        self.write({})

        for obj_inv in self:
            invtype = obj_inv.type
            number = obj_inv.number
            move_id = obj_inv.move_id and obj_inv.move_id.id or False
            reference = obj_inv.reference or ''

            self.write({'internal_number': number})

            if invtype in ('in_invoice', 'in_refund', 'in_debit_note'):
                if not reference:
                    ref = self._convert_ref(number)
                else:
                    ref = reference
            else:
                ref = self._convert_ref(number)

            self._cr.execute("UPDATE account_move SET ref=%s "
                             "WHERE id=%s AND (ref is null OR ref = '')",
                             (ref, move_id))
            self._cr.execute("UPDATE account_move_line SET ref=%s "
                             "WHERE move_id=%s AND (ref is null OR ref = '')",
                             (ref, move_id))
            self._cr.execute("UPDATE account_analytic_line SET ref=%s "
                             "FROM account_move_line moveline "
                             "WHERE moveline.move_id = %s "
                             "AND account_analytic_line.move_id = moveline.id",
                             (ref, move_id))

            for inv_id, name in obj_inv.name_get():
                if obj_inv.type in ('debit_note', 'in_debit_note'):
                    template = _('Debit Note ') + " '%s' " + _("is validated.")
                else:
                    template = _('Invoice ') + " '%s' " + _("is validated.")
                self.message_post(body=(template % name))

            obj_inv.sync_invoice()
            if not obj_inv.reconciled and obj_inv.amount_total == 0.0:
                obj_inv.reconcile_invoice()

            self.set_waybills_as_invoiced(obj_inv)
        return True

    @api.one
    def sync_invoice(self):
        """This method provides an hooking point for other modules to sync
        the invoice with external services or data stores"""
        pass

    # TKO ACCOUNT PT: New method
    def finalize_invoice_move_lines(self, move_lines):
        if self.amount_total == 0.0:
            move_lines.append(move_lines[-1])
        return move_lines

    # TKO ACCOUNT PT: New method
    def pay_zero_invoice(self, cr, uid, invoice, context):
        raise NotImplementedError("This must be fixed or removed.")

    # TKO ACCOUNT PT: New method
    @api.one
    def reconcile_invoice(self):
        lines = self.move_id.line_id
        lines = (lines + self.payment_ids)
        lines = lines.filtered(lambda l: l.account_id == self.account_id)
        lines.reconcile('manual', None, None, None)

    @api.multi
    def action_move_create(self):
        # check for debit notes as well
        group_check_total = self.env.ref(
            'account.group_supplier_inv_check_total')
        if self.env.user in group_check_total.users:
            for inv in self:
                totals_match = abs(inv.check_total - inv.amount_total) >= \
                    (inv.currency_id.rounding / 2.0)
                if inv.type == 'in_debit_note' and totals_match:
                    msg = _('Please verify the price of the invoice!\nThe '
                            'encoded total does not match the computed total.')
                    raise Warning(_('Bad Total!'), msg)
        return super(account_pt_invoice, self).action_move_create()

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        types = {
            'out_invoice': 'Invoice ',
            'in_invoice': 'Supplier Invoice ',
            'out_refund': 'Refund ',
            'in_refund': 'Supplier Refund ',
            'debit_note': 'Debit Note ',
            'in_debit_note': 'Supplier Debit Note',
            'simplified_invoice': 'Simplified Invoice ',
        }
        invoices = self.browse(cr, uid, ids, context=context)
        get_name = lambda inv: inv.number or types[inv.type] + (inv.name or '')
        return [(inv.id, get_name(inv)) for inv in invoices]

    def _prepare_refund(self, cr, uid, invoice, date=None, period_id=None,
                        description=None, journal_id=None, context=None):
        """ This method is overridden to write extra account_pt fields:
            references of invoice and maps account_pt documents
            Prepare the dict of values to create the new refund
            from the invoice.
            This method may be overridden to implement custom
            refund generation (making sure to call super() to establish
            a clean extension chain).

            :param record invoice: invoice to refund
            :param string date: refund creation date from the wizard
            :param integer period_id: force account.period from the wizard
            :param string description: description of the refund from the
                                       wizard
            :param integer journal_id: account.journal from the wizard
            :return: dict of value to create() the refund
        """
        obj_journal = self.pool.get('account.journal')

        type_dict = {
            'out_invoice': 'out_refund',  # Customer Invoice
            'in_invoice': 'in_refund',  # Supplier Invoice
            'out_refund': 'out_invoice',  # Customer Refund
            'in_refund': 'in_invoice',  # Supplier Refund
            'debit_note': 'out_refund',  # Debit Note
            'simplified_invoice': 'out_refund',  # Simplified Invoice
            'in_debit_note': 'in_refund',  # Supplier Debit Note
        }
        invoice_data = {}
        fields = ('name', 'reference', 'comment', 'date_due', 'partner_id',
                  'company_id', 'account_id', 'currency_id', 'origin',
                  'payment_term', 'user_id', 'fiscal_position',
                  'exemption_reason')
        for field in fields:
            if invoice._all_columns[field].column._type == 'many2one':
                invoice_data[field] = invoice[field].id
            else:
                invoice_data[field] = invoice[field]

        invoice_lines = self._refund_cleanup_lines(
            cr, uid, invoice.invoice_line, context=context)

        tax_lines = filter(lambda l: l['manual'], invoice.tax_line)
        tax_lines = self._refund_cleanup_lines(
            cr, uid, tax_lines, context=context)
        if journal_id:
            refund_journal_ids = [journal_id]
        elif invoice['type'] == 'in_invoice':
            refund_journal_ids = obj_journal.search(
                cr, uid, [('type', '=', 'purchase_refund')], context=context)
        else:
            refund_journal_ids = obj_journal.search(
                cr, uid, [('type', '=', 'sale_refund')], context=context)
        if not date:
            date = time.strftime('%Y-%m-%d')
        if refund_journal_ids:
            refund_journal_id = refund_journal_ids[0]
        else:
            refund_journal_id = False
        invoice_data.update({
            'type': type_dict[invoice['type']],
            'date_invoice': date,
            'state': 'draft',
            'number': False,
            'invoice_line': invoice_lines,
            'tax_line': tax_lines,
            'journal_id': refund_journal_id,
        })
        if invoice['type'] in ('out_invoice', 'simplified_invoice'):
            for x, y, line in invoice_data['invoice_line']:
                line.update({
                    'credit_reference': invoice.number,
                    'credit_reason': description,
                })
        if period_id:
            invoice_data['period_id'] = period_id
        if description:
            invoice_data['name'] = description

        return invoice_data

    # notes
    def pay_and_reconcile(self, cr, uid, ids, pay_amount, pay_account_id,
                          period_id, pay_journal_id, writeoff_acc_id,
                          writeoff_period_id, writeoff_journal_id,
                          context=None, name=''):
        if context is None:
            context = {}
        # TODO check if we can use different period for payment and the
        # writeoff move_line
        assert len(ids) == 1, "Can only pay one invoice at a time."
        invoice = self.browse(cr, uid, ids[0], context=context)
        src_account_id = invoice.account_id.id
        # Take the seq as name for move
        # TKO ACCOUNT PT: Change: map simplified invoice and debit notes
        types = {'out_invoice': -1, 'simplified_invoice': -1, 'debit_note': -1,
                 'in_debit_note': -1, 'in_invoice': 1, 'out_refund': 1,
                 'in_refund': -1}
        direction = types[invoice.type]
        # take the choosen date
        if 'date_p' in context and context['date_p']:
            date = context['date_p']
        else:
            date = time.strftime('%Y-%m-%d')

        # Take the amount in currency and the currency of the payment
        amount_currency = context.get('amount_currency', 0.0)
        currency_id = context.get('currency_id', False)

        journal_obj = self.pool.get('account.journal')
        pay_journal = journal_obj.read(cr, uid, pay_journal_id, ['type'])
        valid_types = ('in_invoice', 'out_invoice', 'debit_note',
                       'simplified_invoice', 'in_debit_note')
        if invoice.type in valid_types:
            if pay_journal['type'] == 'bank':
                entry_type = 'bank_pay_voucher'  # Bank payment
            else:
                entry_type = 'pay_voucher'  # Cash payment
        else:
            entry_type = 'cont_voucher'
        if invoice.type in ('in_invoice', 'in_refund', 'in_debit_note'):
            ref = invoice.reference
        else:
            ref = self._convert_ref(invoice.number)
        partner = invoice.partner_id
        if partner.parent_id and not partner.is_company:
            partner = partner.parent_id
        # Pay attention to the sign for both debit/credit AND amount_currency
        l1 = {
            'debit': direction * pay_amount > 0 and direction * pay_amount,
            'credit': direction * pay_amount < 0 and -direction * pay_amount,
            'account_id': src_account_id,
            'partner_id': partner.id,
            'ref': ref,
            'date': date,
            'currency_id': currency_id,
            'amount_currency': direction * amount_currency,
            'company_id': invoice.company_id.id,
        }
        l2 = {
            'debit': direction * pay_amount < 0 and -direction * pay_amount,
            'credit': direction * pay_amount > 0 and direction * pay_amount,
            'account_id': pay_account_id,
            'partner_id': partner.id,
            'ref': ref,
            'date': date,
            'currency_id': currency_id,
            'amount_currency': -direction * amount_currency,
            'company_id': invoice.company_id.id,
        }

        if not name:
            if invoice.invoice_line:
                name = invoice.invoice_line[0].name
            else:
                name = invoice.number
        l1['name'] = name
        l2['name'] = name

        lines = [(0, 0, l1), (0, 0, l2)]
        move = {'ref': ref, 'line_id': lines, 'journal_id': pay_journal_id,
                'period_id': period_id, 'date': date, 'type': entry_type}
        move_obj = self.pool.get('account.move')
        move_line = self.pool.get('account.move.line')
        precision_obj = self.pool.get('decimal.precision')
        move_id = move_obj.create(cr, uid, move, context=context)

        line_ids = []
        total = 0.0
        move_ids = (move_id, invoice.move_id.id)
        lines_ids = move_line.search(cr, uid, [('move_id', 'in', move_ids)])
        lines = move_line.browse(cr, uid, lines_ids)
        for l in lines + invoice.payment_ids:
            if l.account_id.id == src_account_id:
                line_ids.append(l.id)
                total += (l.debit or 0.0) - (l.credit or 0.0)

        inv_id, name = self.name_get(cr, uid, [invoice.id], context=context)[0]
        account_precision = precision_obj.precision_get(cr, uid, 'Account')
        if round(total, account_precision) == 0.0 or writeoff_acc_id:
            move_line.reconcile(
                cr, uid, line_ids, 'manual', writeoff_acc_id,
                writeoff_period_id, writeoff_journal_id, context)
        else:
            code = invoice.currency_id.symbol
            # TODO: use currency's formatting function
            if invoice.type in ('debit_note', 'in_debit_note'):
                msg = _("Debit Note '%s' is paid partially: "
                        "%s%s of %s%s (%s%s remaining)") % \
                       (name, pay_amount, code, invoice.amount_total,
                        code, total, code)
            else:
                msg = _("Invoice '%s' is paid partially: "
                        "%s%s of %s%s (%s%s remaining)") % \
                       (name, pay_amount, code, invoice.amount_total,
                        code, total, code)
            self.message_post(cr, uid, [inv_id], body=msg, context=context)
            move_line.reconcile_partial(cr, uid, line_ids, 'manual', context)

        # Update the stored value (fields.function), so we write to trigger
        # recompute
        self.write(cr, uid, ids, {}, context=context)
        return True

    def action_date_assign(self, cr, uid, ids, *args):
        for inv in self.browse(cr, uid, ids):
            if inv.type != 'simplified_invoice':
                res = self.onchange_payment_term_date_invoice(
                    cr, uid, inv.id, inv.payment_term.id, inv.date_invoice)
                if res and res['value']:
                    self.write(cr, uid, [inv.id], res['value'])
        return True

    # Inherit method t pay account pt documents
    def invoice_pay_customer(self, cr, uid, ids, context=None):
        if not ids:
            return []
        model_obj = self.pool.get('ir.model.data')
        partner_obj = self.pool.get('res.partner')
        dummy, view_id = model_obj.get_object_reference(
            cr, uid, 'account_voucher', 'view_vendor_receipt_dialog_form')

        inv = self.browse(cr, uid, ids[0], context=context)
        partner = partner_obj._find_accounting_partner(inv.partner_id)
        is_refund = inv.type in ('out_refund', 'in_refund')
        amount = inv.residual * (-1 if is_refund else 1)
        out_types = ('out_invoice', 'debit_note',
                     'simplified_invoice', 'out_refund')
        voucher_type = 'receipt' if inv.type in out_types else 'payment'
        return {
            'name': _("Pay Invoice"),
            'view_mode': 'form',
            'view_id': view_id,
            'view_type': 'form',
            'res_model': 'account.voucher',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': {
                'default_partner_id': partner.id,
                'default_amount': amount,
                'default_reference': inv.name,
                'close_after_process': True,
                'invoice_type': inv.type,
                'invoice_id': inv.id,
                'default_type': voucher_type,
                'type': voucher_type,
            }
        }


class account_pt_invoice_line(osv.osv):
    _name = "account.invoice.line"
    _description = "Invoice Line"
    _inherit = 'account.invoice.line'

    def product_id_change(self, cr, uid, ids, product, uom_id, qty=0, name='',
                          type='out_invoice', partner_id=False,
                          fposition_id=False, price_unit=False,
                          currency_id=False, company_id=None, context=None):
        if context is None:
            context = {}
        if company_id is None:
            company_id = context.get('company_id', False)
        context = dict(context)
        context.update({'company_id': company_id, 'force_company': company_id})
        if not partner_id:
            raise osv.except_osv(
                _('No Partner Defined !'),
                _("You must first select a partner !"))
        if not product:
            res = {'value': {}, 'domain': {'product_uom': []}}
            if type not in ('in_invoice', 'in_refund', 'in_debit_note'):
                res['value'] = {'price_unit': 0.0}
            return res
        partner_obj = self.pool.get('res.partner')
        part = partner_obj.browse(cr, uid, partner_id, context=context)
        fpos_obj = self.pool.get('account.fiscal.position')
        if fposition_id:
            fpos = fpos_obj.browse(cr, uid, fposition_id, context=context)
        else:
            fpos = False

        if part.lang:
            context.update({'lang': part.lang})
        result = {}
        product_obj = self.pool.get('product.product')
        account_obj = self.pool.get('account.account')
        uom_obj = self.pool.get('product.uom')
        res = product_obj.browse(cr, uid, product, context=context)

        out_types = ('out_invoice', 'debit_note',
                     'simplified_invoice', 'out_refund')
        if type in out_types:
            a = res.property_account_income.id
            if not a:
                a = res.categ_id.property_account_income_categ.id
        else:
            a = res.property_account_expense.id
            if not a:
                a = res.categ_id.property_account_expense_categ.id
        a = fpos_obj.map_account(cr, uid, fpos, a)
        if a:
            result['account_id'] = a

        result['name'] = res.partner_ref

        if type in out_types:
            res_taxes = res.taxes_id
            if res.description_sale:
                result['name'] += '\n' + res.description_sale
        else:
            res_taxes = res.supplier_taxes_id
            if res.description_purchase:
                result['name'] += '\n' + res.description_purchase

        if res_taxes:
            taxes = res_taxes
        elif a:
            taxes = account_obj.browse(cr, uid, a, context=context).tax_ids
        else:
            taxes = False
        tax_id = fpos_obj.map_tax(cr, uid, fpos, taxes)

        if type in ('in_invoice', 'in_refund'):
            price_unit = price_unit or res.standard_price
        else:
            price_unit = res.list_price
        result.update({
            'price_unit': res.list_price, 'invoice_line_tax_id': tax_id
        })

        result['uos_id'] = uom_id or res.uom_id.id

        domain = {'uos_id': [('category_id', '=', res.uom_id.category_id.id)]}

        res_final = {'value': result, 'domain': domain}

        if not company_id or not currency_id:
            return res_final

        company = self.pool.get('res.company').browse(
            cr, uid, company_id, context=context)
        currency = self.pool.get('res.currency').browse(
            cr, uid, currency_id, context=context)

        if company.currency_id.id != currency.id:
            if type in ('in_invoice', 'in_refund', 'in_debit_note'):
                res_final['value']['price_unit'] = res.standard_price
            new_price = res_final['value']['price_unit'] * currency.rate
            res_final['value']['price_unit'] = new_price

        if result['uos_id'] and result['uos_id'] != res.uom_id.id:
            final_price_unit = res_final['value']['price_unit']
            new_price = uom_obj._compute_price(
                cr, uid, res.uom_id.id, final_price_unit, result['uos_id'])
            res_final['value']['price_unit'] = new_price
        return res_final

    def move_line_get(self, cr, uid, invoice_id, context=None):
        res = []
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        if context is None:
            context = {}
        inv = self.pool.get('account.invoice').browse(
            cr, uid, invoice_id, context=context)
        company_currency = inv.company_id.currency_id.id

        for line in inv.invoice_line:
            mres = self.move_line_get_item(cr, uid, line, context)
            if not mres:
                continue
            res.append(mres)
            tax_code_found = False
            discount = 1.0 - (line['discount'] or 0.0) / 100.0
            base_types = ('out_invoice', 'debit_note',
                          'simplified_invoice', 'in_invoice')
            for tax in tax_obj.compute_all(cr, uid, line.invoice_line_tax_id,
                                           line.price_unit * discount,
                                           line.quantity, line.product_id,
                                           inv.partner_id)['taxes']:

                if inv.type in base_types:
                    tax_code_id = tax['base_code_id']
                    tax_amount = line.price_subtotal * tax['base_sign']
                else:
                    tax_code_id = tax['ref_base_code_id']
                    tax_amount = line.price_subtotal * tax['ref_base_sign']

                if tax_code_found:
                    if not tax_code_id:
                        continue
                    res.append(self.move_line_get_item(cr, uid, line, context))
                    res[-1]['price'] = 0.0
                    res[-1]['account_analytic_id'] = False
                elif not tax_code_id:
                    continue
                tax_code_found = True

                res[-1]['tax_code_id'] = tax_code_id
                res[-1]['tax_amount'] = cur_obj.compute(
                    cr, uid, inv.currency_id.id, company_currency, tax_amount,
                    context={'date': inv.date_invoice})
        return res

    _columns = {
        'credit_reference': fields.char('Invoice Reference', size=256),
        'credit_reason': fields.text('Invoice Reason'),
        'waybill_reference': fields.char('Waybill Reference', size=256),
        'waybill_date': fields.date('Waybill Date'),
        'type': fields.related(
            'invoice_id', 'type', type='char', string="Invoice type",
            size=256),
    }
    _defaults = {
        'sequence': 0,
    }

    def _default_account(self, cr, uid, context=None):
        users_obj = self.pool.get('res.users')
        account_obj = self.pool.get('account.account')
        user_company = users_obj.browse(cr, uid, uid).company_id.id
        query = [('company_id', '=', user_company), ('parent_id', '=', False)]
        account_id = account_obj.search(
            cr, uid, query, limit=1, context=context)
        return account_id and account_id[0] or False

    def create(self, cr, user, vals, context=None):
        context_type = context.get('type') if context else None
        if 'product_id' in vals and context_type != 'in_invoice':
            if not vals['product_id']:
                vals['quantity'] = 0
                vals['account_id'] = self._default_account(cr, user, None)
        return super(account_pt_invoice_line, self).create(
            cr, user, vals, context)

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'credit_reference': False,
            'credit_reason': False,
            'waybill_reference': False,
            'waybill_date': False
        })
        return super(account_pt_invoice_line, self).copy_data(
            cr, uid, id, default, context=context)


class account_pt_invoice_tax(osv.osv):
    _name = "account.invoice.tax"
    _description = "Invoice Tax"
    _inherit = 'account.invoice.tax'

    def _calculate_tax_group(self, cr, uid, invoice, line):
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        cur = invoice.currency_id
        company_currency = invoice.company_id.currency_id.id
        discount = 1 - (line.discount or 0.0) / 100.0
        base_types = ('out_invoice', 'debit_note',
                      'simplified_invoice', 'in_invoice')
        today = time.strftime('%Y-%m-%d')
        date_context = {'date': invoice.date_invoice or today}

        def convert(amount):
            """convert currency"""
            return cur_obj.compute(
                cr, uid, cur.id, company_currency,
                amount, context=date_context,
                round=False)

        for tax in tax_obj.compute_all(cr, uid, line.invoice_line_tax_id,
                                       line.price_unit * discount,
                                       line.quantity, line.product_id,
                                       invoice.partner_id)['taxes']:
            tax['price_unit'] = cur_obj.round(cr, uid, cur, tax['price_unit'])
            val = {
                'invoice_id': invoice.id,
                'name': tax['name'],
                'amount': tax['amount'],
                'manual': False,
                'sequence': tax['sequence'],
                'base': tax['price_unit'] * line['quantity'],
            }
            if invoice.type in base_types:
                account_id = tax['account_collected_id'] or line.account_id.id
                account_analytic_id = tax['account_analytic_collected_id']
                val.update({
                    'base_code_id': tax['base_code_id'],
                    'tax_code_id': tax['tax_code_id'],
                    'base_amount': convert(val['base'] * tax['base_sign']),
                    'tax_amount': convert(val['amount'] * tax['tax_sign']),
                    'account_id': account_id,
                    'account_analytic_id': account_analytic_id,
                })
            else:
                account_id = tax['account_paid_id'] or line.account_id.id
                val.update({
                    'base_code_id': tax['ref_base_code_id'],
                    'tax_code_id': tax['ref_tax_code_id'],
                    'base_amount': convert(val['base'] * tax['ref_base_sign']),
                    'tax_amount': convert(val['amount'] * tax['ref_tax_sign']),
                    'account_id': account_id,
                    'account_analytic_id': tax['account_analytic_paid_id'],
                })
            key = (val['tax_code_id'], val['base_code_id'],
                   val['account_id'], val['account_analytic_id'])
        return key, val

    def compute(self, cr, uid, invoice, context=None):
        tax_grouped = {}
        cur_obj = self.pool.get('res.currency')
        cur = invoice.currency_id

        for line in invoice.invoice_line:
            key, val = self._calculate_tax_group(cr, uid, invoice, line)
            if key not in tax_grouped:
                tax_grouped[key] = val
            else:
                tax_grouped[key]['amount'] += val['amount']
                tax_grouped[key]['base'] += val['base']
                tax_grouped[key]['base_amount'] += val['base_amount']
                tax_grouped[key]['tax_amount'] += val['tax_amount']

        for t in tax_grouped.values():
            t['base'] = cur_obj.round(cr, uid, cur, t['base'])
            t['amount'] = cur_obj.round(cr, uid, cur, t['amount'])
            t['base_amount'] = cur_obj.round(cr, uid, cur, t['base_amount'])
            t['tax_amount'] = cur_obj.round(cr, uid, cur, t['tax_amount'])
        return tax_grouped
