# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./

from openerp.osv import fields, osv
from openerp import fields as new_fields, SUPERUSER_ID
from openerp.tools.translate import _
from openerp.exceptions import UserError, Warning
from openerp import api

from openerp.addons.account.models.account_invoice import TYPE2REFUND
TYPE2REFUND.update({
    'debit_note': 'out_refund',  # Debit Note
    'simplified_invoice': 'out_refund',  # Simplified Invoice
    'in_debit_note': 'in_refund',  # Supplier Debit Note
})

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
    u'Regime particular do tabaco',
])
EXEMPTION_SELECTION = [(str(i), t) for (i, t) in EXEMPTION_REASONS]


def _state_func(state):
    out_types = (
        'out_invoice', 'out_refund',
        'simplified_invoice', 'debit_note',
    )

    def _(self, cr, uid, obj, ctx=None):
        return (obj['state'] == state and obj['type'] in out_types)
    return _


class AccountPtInvoice(osv.osv):
    _name = "account.invoice"
    _description = 'Invoice'
    _inherit = 'account.invoice'
    _order = "date_invoice desc, number desc"
    _track = {
        'type': {
        },
        'state': {
            'account.mt_invoice_paid': _state_func('paid'),
            'account.mt_invoice_validated': _state_func('open'),
            'l10n_pt_account.mt_invoice_canceled': _state_func('cancel'),
        },
    }

    # TKO ACCOUNT PT (v9): Inherit to remove sign of refunds
    @api.one
    @api.depends('invoice_line_ids.price_subtotal',
                 'tax_line_ids.amount', 'currency_id', 'company_id')
    def _compute_amount(self):
        self.amount_untaxed = sum(
            line.price_subtotal for line in self.invoice_line_ids)
        self.amount_tax = sum(line.amount for line in self.tax_line_ids)
        self.amount_total = self.amount_untaxed + self.amount_tax
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        if self.currency_id and\
           self.currency_id != self.company_id.currency_id:
            amount_total_company_signed = self.currency_id.compute(
                self.amount_total, self.company_id.currency_id)
            amount_untaxed_signed = self.currency_id.compute(
                self.amount_untaxed, self.company_id.currency_id)
        self.amount_total_company_signed = amount_total_company_signed
        self.amount_total_signed = self.amount_total
        self.amount_untaxed_signed = amount_untaxed_signed

    def _convert_ref(self, ref):
        return (ref or '').replace('/', '')

    def _check_selection_field_value(self, cr, uid, field,
                                     value, context=None):
        other_types = ('debit_note', 'in_debit_note', 'simplified_invoice')
        if field == 'type' and value in other_types:
            return
        super(AccountPtInvoice, self)._check_selection_field_value(
            cr, uid, field, value, context=context)

    # TKO ACCOUNT PT: Inherit method
    # To clean fields of reference documents from invoice_lines when create
    # refund
    def _refund_cleanup_lines(self, cr, uid, lines, context=None):
        lines = super(AccountPtInvoice, self)._refund_cleanup_lines(
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
        for line in inv.invoice_line_ids:
            account_line = fpos_obj.map_account(
                cr, uid, inv.fiscal_position_id, line.account_id.id)
            client_types = (
                'out_invoice', 'debit_note',
                'simplified_invoice', 'out_refund',
            )
            if inv.type in client_types:
                new_taxes = fpos_obj.map_tax(
                    cr, uid, inv.fiscal_position_id, line.product_id.taxes_id)
            else:
                new_taxes = fpos_obj.map_tax(
                    cr, uid, inv.fiscal_position_id,
                    line.product_id.supplier_taxes_id)
            line_vals = {
                'account_id': account_line,
                'invoice_line_tax_id': [(5,), (6, 0, new_taxes)],
            }
            inv_line_obj.write(cr, uid, [line.id], line_vals)
        account_inv = fpos_obj.map_account(
            cr, uid, inv.fiscal_position_id, inv.account_id.id)
        self.write(cr, uid, [inv.id], {
                   'account_id': account_inv}, context=context)
        return True

    # TKO ACCOUNT PT: New method that gets payment term to simplified invoices
    def _get_payment_term(self, cr, uid, context=None):
        if context and context.get('type') == 'simplified':
            return self.pool.get('account.payment.term').search(
                cr, uid, [('name', '=', 'Pronto Pagamento')])[0]
        else:
            return None

    @api.model
    def _default_journal(self):
        inv_type = self._context.get('type', 'out_invoice')
        if inv_type == 'simplified_invoice':
            user_company_id = self.env.user.company_id.id
            company_id = self._context.get('company_id', user_company_id)
            domain = [
                ('type', '=', 'sale'),
                ('company_id', '=', company_id),
            ]
            return self.env['account.journal'].search(domain, limit=1)
        elif inv_type in ('debit_note', 'in_debit_note'):
            return self.env.ref('l10n_pt_account.debit_note_journal')
        else:
            return super(AccountPtInvoice, self)._default_journal()

    type = new_fields.Selection(selection_add=[
        ('debit_note', "Debit Note"),
        ('in_debit_note', "Supplier Debit Note"),
        ('simplified_invoice', "Simplified Invoice")])

    journal_id = new_fields.Many2one(default=_default_journal)

    _columns = {
        'fiscal_position_id': fields.many2one(
            'account.fiscal.position', 'Fiscal Position', readonly=True,
            states={'draft': [('readonly', False)]}),
        'waybill_ids': fields.one2many(
            'account.guia', 'invoice_id', 'Waybills'),
        'with_transport_info': fields.boolean(
            'Transport Information?', readonly=True,
            states={'draft': [('readonly', False)]}),
        'load_date': fields.datetime(
            'Load date', readonly=True,
            states={'draft': [('readonly', False)]}),
        'unload_date': fields.datetime(
            'Unload date', readonly=True,
            states={'draft': [('readonly', False)]}),
        'load_place': fields.char(
            'Load place', size=256, readonly=True,
            states={'draft': [('readonly', False)]}),
        'unload_place': fields.char(
            'Unload place', size=256, readonly=True,
            states={'draft': [('readonly', False)]}),
        'load_city': fields.char(
            'Load city', size=256, readonly=True,
            states={'draft': [('readonly', False)]}),
        'unload_city': fields.char(
            'Unload city', size=256, readonly=True,
            states={'draft': [('readonly', False)]}),
        'load_postal_code': fields.char(
            'Load postal_code', size=256, readonly=True,
            states={'draft': [('readonly', False)]}),
        'unload_postal_code': fields.char(
            'Unload postal_code', size=256, readonly=True,
            states={'draft': [('readonly', False)]}),
        'car_registration': fields.many2one(
            "account.license_plate", string="License Plate", readonly=True,
            states={'draft': [('readonly', False)]}),
        'exemption_reason': fields.selection(
            EXEMPTION_SELECTION, 'Exemption Reason', readonly=True,
            states={'draft': [('readonly', False)]}),
        'waybill_ref': fields.char(
            string='Reference',
            help="To reference invoice lines you must write waybill number.",
            readonly=True, states={'draft': [('readonly', False)]}),
        'date_invoice': fields.date(
            string='Invoice Date', readonly=True,
            states={
                'draft': [('readonly', False)],
                'proforma': [('readonly', False)],
                'proforma2': [('readonly', False)],
            }, index=True, help="Keep empty to use the current date",
            copy=False),
    }

    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'with_transport_info': False,
            'waybill_ref': False,
            'waybill_ids': False,
        })
        return super(AccountPtInvoice, self).copy(
            cr, uid, id, default, context)

    # TKO ACCOUNT PT: New method
    def _get_client_if_simplified(self, cr, uid, context=None):
        if context and context.get('type') == 'simplified_invoice':
            # to get a database ID from an XML ID
            pool = self.pool.get('ir.model.data')
            client_id = pool.get_object(
                cr, uid, 'l10n_pt_account', 'simplified_invoice_client')
            return client_id.id

    # TKO ACCOUNT PT: New method
    def _get_address_if_simplified(self, cr, uid, context=None):
        if context and context.get('type') == 'simplified_invoice':
            # to get a database ID from an XML ID
            pool = self.pool.get('ir.model.data')
            address_id = pool.get_object(
                cr, uid, 'l10n_pt_account',
                'simplified_invoice_client_address')
            return address_id.id

    # TKO ACCOUNT PT: New method
    def _get_account_if_simplified(self, cr, uid, context=None):
        client_id = self._get_client_if_simplified(cr, uid, context)
        if client_id:
            [client] = self.pool.get(
                'res.partner').browse(cr, uid, [client_id])
            return client.property_account_receivable_id.id

    # TKO ACCOUNT PT: New method
    def _max_amount_simplified_invoices(self, cr, uid, ids):
        for invoice in self.browse(cr, uid, ids):
            if invoice.type == 'simplified_invoice'\
               and invoice.amount_untaxed > 1000:
                return False
        return True

    _defaults = {
        'payment_term': _get_payment_term,
        'partner_id': _get_client_if_simplified,
        #        'address_invoice_id': _get_address_if_simplified,
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

    @api.multi
    def check_simplified_invoice_constraints(self):
        simplified = self.filtered(lambda i: i.type == 'simplified_invoice')
        if any(invoice.amount_total > 1000.0 for invoice in simplified):
            raise UserError(
                _(u"You can't create simplified invoices "
                  u"with a total over 1000€"))

    @api.multi
    def update_lines_waybill_refs(self):
        for invoice in self:
            if invoice.type not in ('out_invoice', 'simplified_invoice'):
                continue
            missing_ref = lambda line: not line.waybill_reference
            lines_without_refs = invoice.invoice_line_ids.filtered(missing_ref)
            if invoice.waybill_ref and any(lines_without_refs):
                waybill = self.env['account.guia'].search(
                    [('numero', '=', invoice.waybill_ref)])
                if waybill:
                    vals = {
                        'waybill_reference': waybill.numero,
                        'waybill_date': waybill.data_carga.split()[0],
                    }
                    lines_without_refs.write(vals)
                else:
                    msg = _('Waybill Reference not found: %s')
                    raise UserError(msg % invoice.waybill_ref)

    @api.model
    def get_transport_fields(self, partner):
        address_id = partner.address_get(['delivery'])['delivery']
        if not address_id:
            values = {}
        address = self.env['res.partner'].browse(address_id)
        values = {
            'unload_city': address.city if address.city else '',
            'unload_postal_code': address.zip if address.zip else '',
        }
        return values

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        original_type = self.type
        if self.type in ('debit_note', 'simplified_invoice'):
            self.type = 'out_invoice'
        super(AccountPtInvoice, self)._onchange_partner_id()
        self.type = original_type
        if self.partner_id:
            transport_fields = self.get_transport_fields(self.partner_id)
            for field, value in transport_fields.items():
                setattr(self, field, value)

    # TKO ACCOUNT PT:Inherit method
    def onchange_company_id(self, cr, uid, ids, company_id, part_id, type,
                            invoice_line_ids, currency_id, context=None):
        val = {}
        dom = {}
        obj_journal = self.pool.get('account.journal')
        account_obj = self.pool.get('account.account')
        inv_line_obj = self.pool.get('account.invoice.line')
        property_obj = self.pool.get('ir.property')
        if company_id and part_id and type:
            acc_id = False
            partner_obj = self.pool.get('res.partner').browse(cr, uid, part_id)
            partner_payable = partner_obj.property_account_payable_id
            partner_receiv = partner_obj.property_account_receivable_id
            different_company = (
                partner_payable and partner_receiv.company_id.id != company_id
                and
                partner_receiv and partner_receiv.company_id.id != company_id
            )
            if different_company:
                rec = property_obj.get(
                    cr, uid, 'property_account_receivable_id', 'res.partner',
                    res_id=part_id, context=context)
                if not rec:
                    rec = property_obj.get(
                        cr, uid, 'property_account_receivable_id',
                        'res.partner', context=context)
                pay = property_obj.get(
                    cr, uid, 'property_account_payable_id', 'res.partner',
                    res_id=part_id, context=context)
                if not pay:
                    rec = property_obj.get(
                        cr, uid, 'property_account_payable_id',
                        'res.partner', context=context)

                if not (rec and pay):
                    raise osv.except_osv(
                        _('Configuration Error!'),
                        _('Cannot find a chart of account, you should '
                          'create one from Settings/Configuration'
                          '/Accounting menu.'))
                out_types = (
                    'out_invoice', 'debit_note',
                    'simplified_invoice', 'out_refund',
                )
                if type in out_types:
                    acc_id = rec.id
                else:
                    acc_id = pay.id
                val = {'account_id': acc_id}
            if ids:
                if company_id:
                    inv_obj = self.browse(cr, uid, ids)
                    for line in inv_obj[0].invoice_line_ids:
                        acc = line.account_id
                        if acc and acc.company_id.id != company_id:
                            query = [
                                ('name', '=', acc.name),
                                ('company_id', '=', company_id),
                            ]
                            result_id = account_obj.search(cr, uid, query)
                            if not result_id:
                                raise osv.except_osv(
                                    _('Configuration Error!'),
                                    _('Cannot find a chart of account, you '
                                      'should create one from Settings'
                                      '/Configuration/Accounting menu.'))
                            inv_line_obj.write(cr, uid, [line.id], {
                                'account_id': result_id[-1]
                            })
            elif invoice_line_ids:
                for inv_line in invoice_line_ids:
                    if inv_line[0] == 6:
                        continue
                    obj_l = account_obj.browse(
                        cr, uid, inv_line[2]['account_id'])
                    if obj_l.company_id.id != company_id:
                        raise osv.except_osv(
                            _('Configuration Error!'),
                            _('Invoice line account\'s company and '
                              'invoice\'s company does not match.'))
                    else:
                        continue
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
            journal_query = [
                ('company_id', '=', company_id),
                ('type', '=', journal_type),
            ]
            journal_ids = obj_journal.search(cr, uid, journal_query)
            if journal_ids:
                val['journal_id'] = journal_ids[0]
            ir_values_obj = self.pool.get('ir.values')
            res_journal_default = ir_values_obj.get(
                cr, uid, 'default', 'type=%s' % (type), ['account.invoice'])
            for r in res_journal_default:
                if r[1] == 'journal_id' and r[2] in journal_ids:
                    val['journal_id'] = r[2]
            if not val.get('journal_id', False):
                msg = _('Cannot find any account journal of %s type '
                        'for this company.\n\nYou can create one in '
                        'the menu: \nConfiguration\Journals\Journals.')
                raise osv.except_osv(
                    _('Configuration Error!'),
                    msg % journal_type)
            dom = {'journal_id':  [('id', 'in', journal_ids)]}
        else:
            journal_ids = obj_journal.search(cr, uid, [])

        return {'value': val, 'domain': dom}

    @api.multi
    def _get_analytic_lines(self):
        lines = super(AccountPtInvoice, self)._get_analytic_lines()
        if self.type in ('debit_note', 'simplified_invoice'):
            for line in lines:
                if 'amount' in line:
                    line['amount'] *= -1
        return lines

    @api.multi
    def compute_invoice_totals(self, company_currency, invoice_move_lines):
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
            if self.type in ('out_invoice', 'in_refund',
                             'debit_note', 'simplified_invoice'):
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
    def invoice_validate(self):
        if not super(AccountPtInvoice, self).invoice_validate():
            return False
        self.check_simplified_invoice_constraints()
        self.update_lines_waybill_refs()
        for obj_inv in self:
            invtype = obj_inv.type
            number = obj_inv.number
            move_id = obj_inv.move_id and obj_inv.move_id.id or False
            reference = obj_inv.reference or ''

            if invtype in ('in_invoice', 'in_refund', 'in_debit_note'):
                if not reference:
                    ref = self._convert_ref(number)
                else:
                    ref = reference
            else:
                ref = self._convert_ref(number)

            self._cr.execute('UPDATE account_move SET ref=%s '
                             'WHERE id=%s AND (ref is null OR ref = \'\')',
                             (ref, move_id))
            self._cr.execute('UPDATE account_move_line SET ref=%s '
                             'WHERE move_id=%s '
                             'AND (ref is null OR ref = \'\')',
                             (ref, move_id))
            self._cr.execute('UPDATE account_analytic_line SET ref=%s '
                             'FROM account_move_line '
                             'WHERE account_move_line.move_id = %s '
                             'AND account_analytic_line.move_id = '
                             '    account_move_line.id',
                             (ref, move_id))

            for inv_id, name in obj_inv.name_get():
                if obj_inv.type in ('debit_note', 'in_debit_note'):
                    message = _('Debit Note ') + " '" + \
                        name + "' " + _("is validated.")
                else:
                    message = _('Invoice ') + " '" + name + \
                        "' " + _("is validated.")
                self.message_post(body=message)

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
    @api.one
    def reconcile_invoice(self):
        same_account = lambda l: l.account_id == self.account_id
        lines = self.move_id.line_id
        lines = (lines + self.payment_ids).filtered(same_account)
        lines.reconcile('manual', None, None, None)

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
        data = self.read(
            cr, uid, ids, ['type', 'number', 'name'],
            context=context, load='_classic_write')
        return [(r['id'], r['number'] or types[r['type']] + r.get('name', ''))
                for r in data]

    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None,
                        description=None, journal_id=None):
        """ Prepare the dict of values to create the new refund
            from the invoice.
            This method may be overridden to implement custom
            refund generation (making sure to call super() to establish
            a clean extension chain).

            :param record invoice: invoice to refund
            :param string date_invoice: refund creation date from the wizard
            :param integer date: force date from the wizard
            :param string description: description of the refund from wizard
            :param integer journal_id: account.journal from the wizard
            :return: dict of value to create() the refund
        """
        values = {}
        for field in ['name', 'reference', 'comment', 'date_due', 'partner_id',
                      'company_id', 'account_id', 'currency_id',
                      'payment_term_id', 'user_id', 'fiscal_position_id',
                      'exemption_reason']:
            if invoice._fields[field].type == 'many2one':
                values[field] = invoice[field].id
            else:
                values[field] = invoice[field] or False

        values['invoice_line_ids'] = self._refund_cleanup_lines(
            invoice.invoice_line_ids)

        tax_lines = filter(lambda l: l.manual, invoice.tax_line_ids)
        values['tax_line_ids'] = self._refund_cleanup_lines(tax_lines)

        if journal_id:
            journal = self.env['account.journal'].browse(journal_id)
        elif invoice['type'] == 'in_invoice':
            journal = self.env['account.journal'].search(
                [('type', '=', 'purchase')], limit=1)
        else:
            journal = self.env['account.journal'].search(
                [('type', '=', 'sale')], limit=1)
        values['journal_id'] = journal.id

        values['type'] = TYPE2REFUND[invoice['type']]
        values['date_invoice'] = date_invoice or new_fields.Date.context_today(
            invoice)
        values['state'] = 'draft'
        values['number'] = False
        values['origin'] = invoice.number

        if invoice['type'] in ('out_invoice', 'simplified_invoice'):
            for x, y, line in values['invoice_line_ids']:
                line.update({
                    'credit_reference': invoice.number,
                    'credit_reason': description,
                })

        if date:
            values['date'] = date
        if description:
            values['name'] = description
        return values

    # Map configurations to extra document types: simplified invoice and debit
    # notes
    def pay_and_reconcile(self, cr, uid, ids, pay_amount, pay_account_id,
                          period_id, pay_journal_id, writeoff_acc_id,
                          writeoff_period_id, writeoff_journal_id,
                          context=None, name=''):
        if context is None:
            context = {}
        # TODO check if we can use different period for payment and the
        # writeoff line
        assert len(ids) == 1, "Can only pay one invoice at a time."
        invoice = self.browse(cr, uid, ids[0], context=context)
        src_account_id = invoice.account_id.id
        # Take the seq as name for move
        # TKO ACCOUNT PT: Change: map simplified invoice and debit notes
        types = {
            'out_invoice': -1, 'simplified_invoice': -1, 'debit_note': -1,
            'in_debit_note': -1, 'in_invoice': 1, 'out_refund': 1,
            'in_refund': -1,
        }
        direction = types[invoice.type]
        # take the choosen date
        if 'date_p' in context and context['date_p']:
            date = context['date_p']
        else:
            date = time.strftime('%Y-%m-%d')

        # Take the amount in currency and the currency of the payment
        if context.get('amount_currency') and context.get('currency_id'):
            amount_currency = context['amount_currency']
            currency_id = context['currency_id']
        else:
            amount_currency = False
            currency_id = False

        pay_journal = self.pool.get('account.journal').read(
            cr, uid, pay_journal_id, ['type'], context=context)
        paid_types = (
            'in_invoice', 'out_invoice', 'debit_note',
            'simplified_invoice', 'in_debit_note',
        )
        if invoice.type in paid_types:
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
            'amount_currency': (amount_currency or 0.0) * direction,
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
            'amount_currency': (amount_currency or 0.0) * -direction,
            'company_id': invoice.company_id.id,
        }

        if not name:
            name = invoice.invoice_line_ids and invoice.invoice_line_ids[
                0].name or invoice.number
        l1['name'] = name
        l2['name'] = name

        lines = [(0, 0, l1), (0, 0, l2)]
        move = {'ref': ref, 'line_id': lines, 'journal_id': pay_journal_id,
                'period_id': period_id, 'date': date, 'type': entry_type}
        move_id = self.pool.get('account.move').create(
            cr, uid, move, context=context)

        line_ids = []
        total = 0.0
        line = self.pool.get('account.move.line')
        move_ids = [move_id, ]
        if invoice.move_id:
            move_ids.append(invoice.move_id.id)
        cr.execute('SELECT id FROM account_move_line '
                   'WHERE move_id IN %s',
                   ((move_id, invoice.move_id.id),))
        lines = line.browse(cr, uid, map(lambda x: x[0], cr.fetchall()))
        for l in lines + invoice.payment_ids:
            if l.account_id.id == src_account_id:
                line_ids.append(l.id)
                total += (l.debit or 0.0) - (l.credit or 0.0)

        inv_id, name = self.name_get(cr, uid, [invoice.id], context=context)[0]
        account_precision = self.pool.get('decimal.precision').precision_get(
            cr, uid, 'Account')
        if (not round(total, account_precision)) or writeoff_acc_id:
            self.pool.get('account.move.line').reconcile(
                cr, uid, line_ids, 'manual', writeoff_acc_id,
                writeoff_period_id, writeoff_journal_id, context)
        else:
            code = invoice.currency_id.symbol
            # TODO: use currency's formatting function
            if invoice.type in ('debit_note', 'in_debit_note'):
                msg = _("Debit Note '%s' is paid partially: "
                        "%s%s of %s%s (%s%s remaining)")
            else:
                msg = _("Invoice '%s' is paid partially: "
                        "%s%s of %s%s (%s%s remaining)")
            msg = msg % (name, pay_amount, code, invoice.amount_total,
                         code, total, code)
            self.message_post(cr, uid, [inv_id], body=msg, context=context)
            self.pool.get('account.move.line').reconcile_partial(
                cr, uid, line_ids, 'manual', context)

        # Update the stored value (fields.function), so we write to trigger
        # recompute
        self.pool.get('account.invoice').write(
            cr, uid, ids, {}, context=context)
        return True

    @api.multi
    def action_date_assign(self):
        for inv in self:
            if inv.type != 'simplified_invoice':
                # Here the onchange will automatically write to the database
                inv._onchange_payment_term_date_invoice()
        return True

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        invoices = self.read(
            cr, uid, ids, ['state', 'internal_number'], context=context)

        for t in invoices:
            if t['state'] not in ('draft', 'cancel', 'proforma', 'proforma2'):
                raise Warning(
                    _('You cannot delete an invoice which is not draft '
                      'or cancelled. You should refund it instead.'))
        return super(AccountPtInvoice, self).unlink(
            cr, uid, ids, context=context)


class AccountPtInvoiceLine(osv.osv):
    _name = "account.invoice.line"
    _description = "Invoice Line"
    _inherit = 'account.invoice.line'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        old_type = self.invoice_id.type
        if self.invoice_id.type in ('simplified_invoice', 'debit_note'):
            self.invoice_id.type = 'out_invoice'
        elif self.invoice_id.type == 'in_debit_note':
            self.invoice_id.type = 'in_invoice'
        res = super(AccountPtInvoiceLine, self)._onchange_product_id()
        if self.invoice_id:
            self.invoice_id.type = old_type
        self.name = self.product_id.partner_ref
        if self.product_id.description:
            self.name += '\n' + self.product_id.description
        return res

    def move_line_get(self, cr, uid, invoice_id, context=None):
        res = []
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        if context is None:
            context = {}
        inv = self.pool.get('account.invoice').browse(
            cr, uid, invoice_id, context=context)
        company_currency = inv.company_id.currency_id.id

        for line in inv.invoice_line_ids:
            mres = self.move_line_get_item(cr, uid, line, context)
            if not mres:
                continue
            res.append(mres)
            tax_code_found = False
            computed_taxes = tax_obj.compute_all(
                cr, uid, line.invoice_line_tax_id,
                (line.price_unit * (1.0 - (line['discount'] or 0.0) / 100.0)),
                line.quantity, line.product_id,
                inv.partner_id)['taxes']
            for tax in computed_taxes:

                if inv.type in ('out_invoice', 'debit_note',
                                'simplified_invoice', 'in_invoice'):
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
            'invoice_id', 'type', type='char',
            string="Invoice type", size=256),
    }
    _defaults = {
        'sequence': 0,
    }

    def create(self, cr, user, vals, context=None):
        not_product = ('product_id' in vals and not vals['product_id'])
        different_type = (context and 'type' in context
                          and context['type'] != 'in_invoice')
        if not_product and different_type:
            vals['quantity'] = 0
            vals['account_id'] = self._default_account(cr, user, None)
        return super(AccountPtInvoiceLine, self).create(
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
        return super(AccountPtInvoiceLine, self).copy_data(
            cr, uid, id, default, context=context)


class AccountPtInvoiceTax(osv.osv):
    _name = "account.invoice.tax"
    _description = "Invoice Tax"
    _inherit = 'account.invoice.tax'

    def compute(self, cr, uid, invoice, context=None):
        tax_grouped = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        cur = invoice.currency_id
        company_currency = invoice.company_id.currency_id.id

        for line in invoice.invoice_line_ids:
            computed_taxes = tax_obj.compute_all(
                cr, uid, line.invoice_line_tax_id,
                (line.price_unit * (1 - (line.discount or 0.0) / 100.0)),
                line.quantity, line.product_id, invoice.partner_id)['taxes']
            for tax in computed_taxes:
                tax['price_unit'] = cur_obj.round(
                    cr, uid, cur, tax['price_unit'])
                val = {}
                val['invoice_id'] = invoice.id
                val['name'] = tax['name']
                val['amount'] = tax['amount']
                val['manual'] = False
                val['sequence'] = tax['sequence']
                val['base'] = tax['price_unit'] * line['quantity']
                today = time.strftime('%Y-%m-%d')
                if invoice.type in ('out_invoice', 'debit_note',
                                    'simplified_invoice', 'in_invoice'):
                    val['base_code_id'] = tax['base_code_id']
                    val['tax_code_id'] = tax['tax_code_id']
                    val['base_amount'] = cur_obj.compute(
                        cr, uid, invoice.currency_id.id, company_currency,
                        val['base'] * tax['base_sign'],
                        context={'date': invoice.date_invoice or today},
                        round=False)
                    val['tax_amount'] = cur_obj.compute(
                        cr, uid, invoice.currency_id.id, company_currency,
                        val['amount'] * tax['tax_sign'],
                        context={'date': invoice.date_invoice or today},
                        round=False)
                    val['account_id'] = tax[
                        'account_collected_id'] or line.account_id.id
                    val['account_analytic_id'] = tax[
                        'account_analytic_collected_id']
                else:
                    val['base_code_id'] = tax['ref_base_code_id']
                    val['tax_code_id'] = tax['ref_tax_code_id']
                    val['base_amount'] = cur_obj.compute(
                        cr, uid, invoice.currency_id.id, company_currency,
                        val['base'] * tax['ref_base_sign'],
                        context={'date': invoice.date_invoice or today},
                        round=False)
                    val['tax_amount'] = cur_obj.compute(
                        cr, uid, invoice.currency_id.id, company_currency,
                        val['amount'] * tax['ref_tax_sign'],
                        context={'date': invoice.date_invoice or today},
                        round=False)
                    val['account_id'] = tax[
                        'account_paid_id'] or line.account_id.id
                    val['account_analytic_id'] = tax[
                        'account_analytic_paid_id']
                key = (val['tax_code_id'],
                       val['base_code_id'],
                       val['account_id'])
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
