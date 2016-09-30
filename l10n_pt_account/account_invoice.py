# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./

from openerp import models, fields, api, _
from openerp.exceptions import UserError, Warning

from openerp.addons.account.models.account_invoice import TYPE2REFUND


TYPE2REFUND.update({
    'debit_note': 'out_refund',  # Debit Note
    'simplified_invoice': 'out_refund',  # Simplified Invoice
    'in_debit_note': 'in_refund',  # Supplier Debit Note
})

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


class AccountPtInvoice(models.Model):
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

    @api.model
    def _check_selection_field_value(self, field, value):
        other_types = ('debit_note', 'in_debit_note', 'simplified_invoice')
        if field == 'type' and value in other_types:
            return
        super(AccountPtInvoice, self)._check_selection_field_value(
            field, value)

    # TKO ACCOUNT PT: Inherit method
    # To clean fields of reference documents from invoice_lines when create
    # refund
    @api.model
    def _refund_cleanup_lines(self, lines):
        lines = super(AccountPtInvoice, self)._refund_cleanup_lines(lines)
        for x, y, line in lines:
            if 'waybill_reference' in line:
                line['waybill_reference'] = False
            if 'waybill_date' in line:
                line['waybill_date'] = False
        return lines

    # TKO ACCOUNT PT: New method that changes accounts from fiscal position
    @api.multi
    def button_change_fiscal_position(self):
        fpos_obj = self.env['account.fiscal.position']

        for line in self.invoice_line_ids:
            account_line = fpos_obj.map_account(
                self.fiscal_position_id, line.account_id.id)
            client_types = (
                'out_invoice', 'debit_note',
                'simplified_invoice', 'out_refund',
            )
            if self.type in client_types:
                new_taxes = fpos_obj.map_tax(
                    self.fiscal_position_id, line.product_id.taxes_id)
            else:
                new_taxes = fpos_obj.map_tax(
                    self.fiscal_position_id,
                    line.product_id.supplier_taxes_id)
            line.write({
                'account_id': account_line,
                'invoice_line_tax_id': [(5,), (6, 0, new_taxes)],
            })
        account_inv = fpos_obj.map_account(
            self.fiscal_position_id, self.account_id.id)
        self.write({'account_id': account_inv})
        return True

    # TKO ACCOUNT PT: New method that gets payment term to simplified invoices
    @api.model
    def _get_payment_term(self):
        context = self.env.context
        if context and context.get('type') == 'simplified':
            return self.env['account.payment.term'].search(
                [('name', '=', 'Pronto Pagamento')], limit=1)
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

    type = fields.Selection(selection_add=[
        ('debit_note', "Debit Note"),
        ('in_debit_note', "Supplier Debit Note"),
        ('simplified_invoice', "Simplified Invoice")])
    journal_id = fields.Many2one(default=_default_journal)
    fiscal_position_id = fields.Many2one(
        'account.fiscal.position', string='Fiscal Position', readonly=True,
        states={'draft': [('readonly', False)]})
    waybill_ids = fields.One2many(
        'account.guia', 'invoice_id', string='Waybills')
    with_transport_info = fields.Boolean(
        string='Transport Information?', readonly=True,
        states={'draft': [('readonly', False)]})
    load_date = fields.Datetime(
        string='Load date', readonly=True,
        states={'draft': [('readonly', False)]},
        default=fields.Datetime.now)
    unload_date = fields.Datetime(
        string='Unload date', readonly=True,
        states={'draft': [('readonly', False)]},
        default=fields.Datetime.now)
    load_place = fields.Char(
        string='Load place', size=256, readonly=True,
        states={'draft': [('readonly', False)]},
        default=u"N/ Armazém")
    unload_place = fields.Char(
        string='Unload place', size=256, readonly=True,
        states={'draft': [('readonly', False)]},
        default='Morada Cliente')
    load_city = fields.Char(
        string='Load city', size=256, readonly=True,
        states={'draft': [('readonly', False)]})
    unload_city = fields.Char(
        string='Unload city', size=256, readonly=True,
        states={'draft': [('readonly', False)]})
    load_postal_code = fields.Char(
        string='Load postal_code', size=256, readonly=True,
        states={'draft': [('readonly', False)]})
    unload_postal_code = fields.Char(
        string='Unload postal_code', size=256, readonly=True,
        states={'draft': [('readonly', False)]})
    car_registration = fields.Many2one(
        "account.license_plate", string="License Plate", readonly=True,
        states={'draft': [('readonly', False)]})
    exemption_reason = fields.Selection(
        EXEMPTION_SELECTION, string='Exemption Reason', readonly=True,
        states={'draft': [('readonly', False)]})
    waybill_ref = fields.Char(
        string='Reference',
        help="To reference invoice lines you must write waybill number.",
        readonly=True, states={'draft': [('readonly', False)]})
    date_invoice = fields.Date(
        string='Invoice Date', readonly=True,
        states={
            'draft': [('readonly', False)],
            'proforma': [('readonly', False)],
            'proforma2': [('readonly', False)],
        }, index=True, help="Keep empty to use the current date",
        copy=False)
    payment_term = fields.Many2one(default=_get_payment_term)
    partner_id = fields.Many2one(default=_get_client_if_simplified)
    account_id = fields.Many2one(default=_get_account_if_simplified)

    @api.multi
    def copy(self, default=None):
        default = dict(default) if default else {}
        default.update({
            'with_transport_info': False,
            'waybill_ref': False,
            'waybill_ids': False,
        })
        return super(AccountPtInvoice, self).copy(default)

    # TKO ACCOUNT PT: New method
    @api.model
    def _get_client_if_simplified(self):
        context = self.env.context
        if context and context.get('type') == 'simplified_invoice':
            # to get a database ID from an XML ID
            client = self.env.ref('l10n_pt_account.simplified_invoice_client')
            return client

    # TKO ACCOUNT PT: New method
    @api.model
    def _get_address_if_simplified(self):
        context = self.env.context
        if context and context.get('type') == 'simplified_invoice':
            # to get a database ID from an XML ID
            address = self.env.ref(
                'l10n_pt_account.simplified_invoice_client_address')
            return address

    # TKO ACCOUNT PT: New method
    @api.model
    def _get_account_if_simplified(self):
        client = self._get_client_if_simplified()
        if client:
            return client.property_account_receivable_id

    # TKO ACCOUNT PT: New method
    @api.multi
    @api.constrains('amount_total', 'state')
    def _max_amount_simplified_invoices(self):
        msg = _("The Simplified Invoices can only have a total up to 1000€")
        for invoice in self:
            if invoice.type == 'simplified_invoice'\
               and invoice.amount_untaxed > 1000:
                raise Warning(msg)

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
            lines_without_refs = invoice.invoice_line_ids.filtered(
                lambda line: not line.waybill_reference)
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
        obj_inv = obj_inv.sudo()
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
        lines = self.move_id.line_id
        lines = (lines + self.payment_ids).filtered(
            lambda l: l.account_id == self.account_id)
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
        values['date_invoice'] = date_invoice or fields.Date.context_today(
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
    @api.v8
    def pay_and_reconcile(self, pay_journal, pay_amount=None, date=None,
                          writeoff_acc=None):
        """ Create and post an account.payment for the invoice self, which
            creates a journal entry that reconciles the invoice.

            :param pay_journal: journal in which the payment entry
                                will be created
            :param pay_amount: amount of the payment to register,
                               defaults to the residual of the invoice
            :param date: payment date, defaults to
                         fields.Date.context_today(self)
            :param writeoff_acc: account in which to create a writeoff if
                                 pay_amount < self.residual, so that the
                                 invoice is fully paid
        """
        assert len(self) == 1, "Can only pay one invoice at a time."
        inbound_types = ('out_invoice', 'in_refund', 'simplified_invoice')
        if self.type in inbound_types:
            payment_method = self.env.ref(
                'account.account_payment_method_manual_in')
            journal_payment_methods = pay_journal.inbound_payment_method_ids
        else:
            payment_method = self.env.ref(
                'account.account_payment_method_manual_out')
            journal_payment_methods = pay_journal.outbound_payment_method_ids
        if payment_method not in journal_payment_methods:
            msg = _('No appropriate payment method enabled on journal %s')
            raise UserError(msg % pay_journal.name)

        payment_type = 'inbound' if self.type in inbound_types else 'outbound'
        supplier_type = self.type in ('in_invoice', 'in_refund')
        client_type = self.type in ('out_invoice', 'out_refund',
                                    'simplified_invoice')
        payment = self.env['account.payment'].create({
            'invoice_ids': [(6, 0, self.ids)],
            'amount': pay_amount or self.residual,
            'payment_date': date or fields.Date.context_today(self),
            'communication': self.reference if supplier_type else self.number,
            'partner_id': self.partner_id.id,
            'partner_type': 'customer' if client_type else 'supplier',
            'journal_id': pay_journal.id,
            'payment_type': payment_type,
            'payment_method_id': payment_method.id,
            'payment_difference_handling': (writeoff_acc and 'reconcile' or
                                            'open'),
            'writeoff_account_id': writeoff_acc and writeoff_acc.id or False,
        })
        payment.post()

    @api.multi
    def action_date_assign(self):
        for inv in self:
            if inv.type != 'simplified_invoice':
                # Here the onchange will automatically write to the database
                inv._onchange_payment_term_date_invoice()
        return True

    @api.multi
    def unlink(self):
        allowed_states = ('draft', 'cancel', 'proforma', 'proforma2')
        for invoice in self:
            if invoice.state not in allowed_states:
                raise Warning(
                    _('You cannot delete an invoice which is not draft '
                      'or cancelled. You should refund it instead.'))
        return super(AccountPtInvoice, self).unlink()


class AccountPtInvoiceLine(models.Model):
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

    credit_reference = fields.Char(string='Invoice Reference', size=256)
    credit_reason = fields.Text(string='Invoice Reason')
    waybill_reference = fields.Char(string='Waybill Reference', size=256)
    waybill_date = fields.Date('Waybill Date')

    @api.model
    def create(self, vals):
        context = self.env.context
        not_product = ('product_id' in vals and not vals['product_id'])
        different_type = (context and 'type' in context and
                          context['type'] != 'in_invoice')
        if not_product and different_type:
            vals['quantity'] = 0
            vals['account_id'] = self._default_account(None)
        return super(AccountPtInvoiceLine, self).create(vals)

    @api.multi
    def copy_data(self, default=None):
        if not default:
            default = {}
        default.update({
            'credit_reference': False,
            'credit_reason': False,
            'waybill_reference': False,
            'waybill_date': False
        })
        return super(AccountPtInvoiceLine, self).copy_data(default)
