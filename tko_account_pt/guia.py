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
from openerp import tools
import openerp.addons.decimal_precision as dp
from datetime import datetime, date, timedelta
import time
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, \
    DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _

HOLIDAYS = set([
    (1, 1),  # Ano Novo
    (4, 25),  # Dia da Liberdade
    (5, 1),  # Dia do Trabalhador
    (6, 10),  # Dia de Portugal
    (8, 15),  # Assunção de Nossa Senhora
    (12, 8),  # Imaculada Conceição
    (12, 25),  # Natal
])


def is_holiday(day):
    if (day.month, day.day) in HOLIDAYS:
        return True
    # Calculate Easter
    # from
    # http://www.forma-te.com/mediateca/download-document/5855-como-calcular-os-feriados-moveis.html
    X, Y = 24, 5
    a = day.year % 19
    b = day.year % 4
    c = day.year % 7
    d = (19 * a + X) % 30
    e = (2 * b + 4 * c + 6 * d + Y) % 7
    easter = date(day.year, 4, d + e - 9) if d + \
        e > 9 else date(day.year, 3, d + e + 22)
    sexta_feira_santa = easter - timedelta(days=2)
    return d in (easter, sexta_feira_santa)


def _now(*a):
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _end_of_today(*a):
    return datetime.now().strftime("%Y-%m-%d 22:59:59")


class account_guia(osv.osv):
    _name = "account.guia"
    _rec_name = "numero"
    _description = "Guia"
    _order = "numero desc, data_carga desc"
    _inherit = ['mail.thread']  # To add message thread

    in_state = lambda s: lambda self, cr, uid, obj, ctx=None: obj['state'] == s
    _track = {
        'type': {
        },
        'state': {
            'tko_account_pt.mt_waybill_canceled': in_state('cancelada'),
            'tko_account_pt.mt_waybill_validated': in_state('arquivada'),
        },
    }

    def create(self, cr, uid, vals, context=None):
        if 'partner_id' in vals:
            delivery_values = self.onchange_partner_id(
                cr, uid, [], vals['partner_id'])['value']
            vals.update(delivery_values)
        return super(account_guia, self).create(cr, uid, vals, context=context)

    def onchange_partner_id(self, cr, uid, ids, partner_id):
        partner_pool = self.pool.get('res.partner')
        if partner_id:
            address_id = partner_pool.address_get(
                cr, uid, [partner_id], ['delivery'])['delivery']
            if not address_id:
                return {}
            [address] = partner_pool.browse(cr, uid, [address_id])
            values = {
                'cidade_entrega': address.city if address.city else '',
                'codigo_postal_entrega': address.zip if address.zip else '',
            }
            return {'value': values}
        else:
            return {}

    def _get_currency(self, cr, uid, context=None):
        user_obj = self.pool.get('res.users')
        currency_obj = self.pool.get('res.currency')
        user = user_obj.browse(
            cr, uid, uid, context=context)
        if user.company_id:
            return user.company_id.currency_id.id
        return currency_obj.search(cr, uid, [('rate', '=', 1.0)])[0]

    def _get_type(self, cr, uid, context=None):
        if 'search_default_remessa' in context:
            return "remessa"
        if 'search_default_transporte' in context:
            return "transporte"
        if 'search_default_devolucao' in context:
            return "devolucao"

    def _get_invoice_line(self, cr, uid, ids, context=None):
        result = set()
        guia_line_obj = self.pool.get('account.linha.guia')
        for line in guia_line_obj.browse(cr, uid, ids, context=context):
            result.add(line.guia_id.id)
        return list(result)

    def _amount_all(self, cr, uid, ids, name, args, context=None):
        res = {}
        for guia in self.browse(cr, uid, ids, context=context):
            res[guia.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0
            }
            for line in guia.linhas_guia:
                res[guia.id]['amount_untaxed'] += line.price_subtotal
            # for line in invoice.tax_line:
            #    res[invoice.id]['amount_tax'] += line.amount
            res[guia.id]['amount_total'] = res[guia.id][
                'amount_tax'] + res[guia.id]['amount_untaxed']
        return res

    def add_five_weekdays(self, starting_date):
        one_day = timedelta(days=1)
        weekdays_to_add = 5
        current_date = starting_date
        while weekdays_to_add > 0:
            current_date += one_day
            if current_date.weekday() >= 5 or is_holiday(current_date):
                continue
            weekdays_to_add -= 1
        return current_date

    def _deadline(self, cr, uid, ids, name, args, context=None):
        res = {}
        for waybill in self.browse(cr, uid, ids, context=context):
            if waybill.validation_date:
                validation_date = datetime.strptime(
                    waybill.validation_date, DEFAULT_SERVER_DATETIME_FORMAT)
                deadline = self.add_five_weekdays(validation_date.date())
            else:
                deadline = date.today()
            res[waybill.id] = deadline.strftime(DEFAULT_SERVER_DATE_FORMAT)
        return res

    def _overdue(self, cr, uid, ids, name, args, context=None):
        res = {}
        for waybill in self.browse(cr, uid, ids, context=context):
            deadline = datetime.strptime(
                waybill.invoice_deadline, DEFAULT_SERVER_DATE_FORMAT).date()
            res[waybill.id] = (deadline - date.today()).days
        return res

    def _same_ids(self, cr, uid, ids, context=None):
        return ids

    READONLY_STATES = {'arquivada': [('readonly', True)],
                       'cancelada': [('readonly', True)]}
    _columns = {
        "numero": fields.char("Numero", size=64, readonly=True),
        "tipo": fields.selection(
            [("remessa", "Remessa"),
             ("transporte", "Transporte"),
             ("devolucao", "Devolução")],
            "Tipo de Guia", required=True, select=1,
            states=READONLY_STATES),
        "state": fields.selection(
            [("aberta", "Aberta"),
             ("arquivada", "Arquivada"),
             ("cancelada", "Cancelada")],
            "Estado", required=True, select=1, readonly=True),
        "data_carga": fields.datetime(
            "Data de Carga", required=True, select=1,
            states=READONLY_STATES),
        "data_descarga": fields.datetime(
            "Data da Descarga", select=1,
            states=READONLY_STATES),
        "partner_id": fields.many2one(
            "res.partner", "Cliente", required=True,
            states=READONLY_STATES),
        "local_carga": fields.char(
            "Local de Carga", size=64, select=1,
            states=READONLY_STATES),
        "local_entrega": fields.char(
            "Local de Descarga", size=64, select=1,
            states=READONLY_STATES),
        'cidade_carga': fields.char(
            "Cidade de Carga", size=64, select=1,
            states=READONLY_STATES),
        "cidade_entrega": fields.char(
            "Cidade de Descarga", size=64, select=1,
            states=READONLY_STATES),
        "codigo_postal_carga": fields.char(
            "Codigo Postal de Carga", size=64, select=1,
            states=READONLY_STATES),
        "codigo_postal_entrega": fields.char(
            "Codigo Postal de Descarga", size=64, select=1,
            states=READONLY_STATES),
        "matricula": fields.many2one(
            "account.license_plate", u"Matrícula", select=1,
            states=READONLY_STATES),
        "linhas_guia": fields.one2many(
            "account.linha.guia", "guia_id", "Linhas Guia",
            states=READONLY_STATES),
        'company_id': fields.many2one(
            'res.company', 'Company', required=True, change_default=True,
            readonly=True),
        "observacoes": fields.text(u"Descrição", select=1),
        'currency_id': fields.many2one(
            'res.currency', 'Currency', required=True, readonly=True),
        'stock_picking_ids': fields.one2many(
            'stock.picking', 'waybill_id', 'Pickings'),
        "sale_id": fields.many2one("sale.order", "Ordem de Venda"),
        'invoice_id': fields.many2one('account.invoice', "Fatura"),
        'invoice_state': fields.selection(
            [('none', 'Não Faturado'), ('invoiced', 'Faturado')],
            "Faturação", readonly=True),
        'origin': fields.char(
            'Origem', size=128,
            help="Referência do documento que deu origem à guia.", select=True,
            states=READONLY_STATES),
        'user_id': fields.many2one(
            'res.users', 'User', readonly=True, states=READONLY_STATES),
        'name': fields.char(
            'Client Reference', size=128, states=READONLY_STATES),
        'amount_untaxed': fields.function(
            _amount_all, digits_compute=dp.get_precision('Account'),
            string='Subtotal', track_visibility='always',
            store={
                'account.guia': (_same_ids, ['linhas_guia'], 20),
                'account.linha.guia': (_get_invoice_line,
                                       ['price_unit', 'invoice_line_tax_id',
                                        'quantity', 'discount', 'guia_id'],
                                       20),
            }, multi='all'),
        'amount_tax': fields.function(
            _amount_all, digits_compute=dp.get_precision('Account'),
            string='Tax', store={
                'account.invoice': (_same_ids, ['linhas_guia'], 20),
                'account.linha.guia': (_get_invoice_line,
                                       ['price_unit', 'invoice_line_tax_id',
                                        'quantity', 'discount', 'guia_id'],
                                       20),
            }, multi='all'),
        'amount_total': fields.function(
            _amount_all, digits_compute=dp.get_precision('Account'),
            string='Total', store={
                'account.invoice': (_same_ids, ['linhas_guia'], 20),
                'account.linha.guia': (_get_invoice_line,
                                       ['price_unit', 'invoice_line_tax_id',
                                        'quantity', 'discount', 'guia_id'],
                                       20),
            }, multi='all'),
        "validation_date": fields.datetime("Date of validation", select=1),
        'days_to_invoice': fields.function(
            _overdue, type='integer', string="Days to invoice",
            help="Number of days to invoice the waybill"),
        'invoice_deadline': fields.function(
            _deadline, type='date', string="Deadline",
            help="Deadline to invoice the waybill"),
    }

    def _default_company_id(self, cr, uid, context=None):
        return self.pool.get('res.company')._company_default_get(
            cr, uid, 'account.guia', context=context),

    _defaults = {
        "state": lambda * x: 'aberta',
        'currency_id': _get_currency,
        'company_id': _default_company_id,
        'local_carga': "N/ Armazém",
        'local_entrega': "Morada Cliente",
        'data_carga': _now,
        'data_descarga': _end_of_today,
        'tipo': _get_type,
        'invoice_state': 'none',
        'user_id': lambda s, cr, u, c: u,
    }

    _order = "data_carga desc, numero desc"

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        guias = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for t in guias:
            if t['state'] in ('aberta'):
                unlink_ids.append(t['id'])
            else:
                raise osv.except_osv(
                    _('Invalid Action!'),
                    _('It isn\'t possible to delete archives waybills.'))
        osv.osv.unlink(self, cr, uid, unlink_ids, context=context)
        return True

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default.update({
            'numero': False,
            'invoice_state': 'none',
            'invoice_id': False,
            'stock_picking_ids': False,
            'sale_id': False,
        })
        return super(account_guia, self).copy(cr, uid, id, default, context)

    def _invoice_line_sale_hook(self, cursor, user, picking, invoice_line_id):
        sale_line_obj = self.pool.get('sale.order.line')
        if picking.sale_line_id:
            vals = {
                'invoiced': True,
                'invoice_lines': [(4, invoice_line_id)]
            }
            sale_line_obj.write(cursor, user, [picking.sale_line_id.id], vals)
        return super(account_guia, self)._invoice_line_hook(
            cursor, user, picking, invoice_line_id)

    def _prepare_invoice_group(self, cr, uid, guia, partner, invoice,
                               context=None):
        """ Builds the dict for grouped invoices
            @param picking: picking object
            @param partner: object of the partner to invoice (not used here,
                            but may be usefull if this function is inherited)
            @param invoice: object of the invoice that we are updating
            @return: dict that will be used to update the invoice
        """
        name = u', '.join(f for f in (invoice.name, guia.name) if f)
        origin = u', '.join(f for f in (invoice.origin, guia.numero) if f)
        if guia.origin:
            origin += u':' + guia.origin
        comment = u'\n'.join(f for f in (invoice.comment, guia.numero) if f)
        waybill_ref = guia.numero
        if invoice.waybill_ref:
            waybill_ref += u',' + invoice.waybill_ref
        invoice_vals = {
            'name': name,
            'origin': origin,
            'comment': comment,
            'date_invoice': context.get('date_inv', False),
            'user_id': uid,
            'waybill_ids': [(4, guia.id)],
            'waybill_ref': waybill_ref,
        }
        if guia.stock_picking_ids:
            for pick in guia.stock_picking_ids:
                if pick.sale_id:
                    if pick.sale_id.client_order_ref:
                        invoice_vals['name'] = pick.sale_id.client_order_ref +\
                            u', ' + invoice_vals['name']
                    if pick.sale_id.note:
                        invoice_vals['comment'] += u"\n" + pick.sale_id.note
                    if pick.sale_id.origin:
                        invoice_vals['origin'] += ': ' + pick.sale_id.origin
        return invoice_vals

    def action_invoice_onguia(self, cr, uid, ids, context=None):
        inv_obj = self.pool.get('account.invoice')
        inv_line_obj = self.pool.get('account.invoice.line')
        picking_obj = self.pool.get('stock.picking')
        invoices_group = {}
        invoices = []
        if context is None:
            context = {}
        inv_type = context.get('type', False)
        group = context.get('group', False)
        if not inv_type:
            raise osv.except_osv(_('Error !'), _('Tipo de Fatura'))
        for guia in self.browse(cr, uid, ids, context=context):
            partner = guia.partner_id
            if partner.parent_id and not partner.is_company:
                partner = partner.parent_id
            if guia.state != 'arquivada' or \
               guia.invoice_state != 'none' or \
               guia.tipo not in ('remessa', 'transporte'):
                continue
            if group and partner.id in invoices_group:
                invoice_id = invoices_group[partner.id]
                invoice = inv_obj.browse(cr, uid, invoice_id)
                invoice_vals_group = self._prepare_invoice_group(
                    cr, uid, guia, partner, invoice, context)
                inv_obj.write(
                    cr, uid, [invoice_id], invoice_vals_group, context=context)
            else:
                # create invoice
                invoice_vals = self._prepare_invoice(
                    cr, uid, guia, partner, context=context)
                invoice_id = inv_obj.create(
                    cr, uid, invoice_vals, context=context)
                invoices.append(invoice_id)
                invoices_group[partner.id] = invoice_id

            if guia.stock_picking_ids:
                for picking in guia.stock_picking_ids:
                    picking_obj._invoice_hook(cr, uid, picking, invoice_id)
            # create invoice lines
            for line in guia.linhas_guia:
                vals = self._prepare_invoice_line(
                    cr, uid, group, line, invoice_id, invoice_vals,
                    context=context)
                if not vals:
                    continue
                invoice_line_id = inv_line_obj.create(cr, uid, vals, context)
                # afect invoice lines of sale order associated to waybill
                # picking
                if line.move_line_id:
                    picking_obj._invoice_line_hook(
                        cr, uid, line.move_line_id, invoice_line_id)
            inv_obj.button_compute(cr, uid, [invoice_id])
            self.write(cr, uid, [guia.id], {'invoice_id': invoice_id})
            # write invoice in related pickings
            if guia.stock_picking_ids:
                picks_ids = [p.id for p in guia.stock_picking_ids
                             if p.invoice_state not in ('invoiced', 'none')]
                pick_vals = {'invoice_state': 'invoiced'}
                picking_obj.write(cr, uid, picks_ids, pick_vals)
        action_model = False
        action = {}
        data_pool = self.pool.get('ir.model.data')
        if inv_type == 'out_invoice':
            action_model, action_id = data_pool.get_object_reference(
                cr, uid, 'account', "action_invoice_tree1")
        elif inv_type == 'simplified_invoice':
            action_model, action_id = data_pool.get_object_reference(
                cr, uid, 'tko_account_pt', "action_simplified_invoice_tree")
        if action_model:
            action_pool = self.pool.get(action_model)
            action = action_pool.read(cr, uid, action_id, context=context)
            domain = [('id', 'in', invoices)]
            action['domain'] = str(domain)
        return action

    def _prepare_invoice(self, cr, uid, guia, partner, context=None):
        """Prepare the dict of values to create the new invoice for a
           waybill.

           :param browse_record guia: guia record to invoice
           :param list(int) line: list of invoice line IDs that must be
                                  attached to the invoice
           :return: dict of value to create() the invoice
        """
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        fpos_obj = self.pool.get('account.fiscal.position')
        partner_obj = self.pool.get('res.partner')
        query = [('type', '=', 'sale'),
                 ('company_id', '=', guia.company_id.id)]
        journal_ids = journal_obj.search(cr, uid, query, limit=1)
        if not journal_ids:
            raise osv.except_osv(
                _('Error !'),
                _('There is no sales journal defined for this company: '
                  '"%s" (id:%d)') % (guia.company_id.name, guia.company_id.id))
        inv_type = context.get('type', False)
        if not inv_type:
            raise osv.except_osv(_('Error !'),
                                 _('Tipo de Fatura'))
        partner_addr = partner_obj.address_get(
            cr, uid, [partner.id], ['invoice'])
        if partner.property_payment_term:
            payment_term_id = partner.property_payment_term.id
        else:
            payment_term_id = False
        if partner.property_account_position:
            account_position_id = partner.property_account_position.id
        else:
            account_position_id = False
        today = time.strftime('%Y-%m-%d')
        invoice_vals = {
            'name': guia.name or '',
            'origin': guia.numero or '',
            'type': inv_type,
            'reference': guia.numero or '',
            'account_id': partner.property_account_receivable.id,
            'partner_id': partner_addr['invoice'] or partner.id,
            'journal_id': journal_ids[0],
            'currency_id': guia.currency_id and guia.currency_id.id or False,
            'comment': guia.numero or '',
            'payment_term': payment_term_id,
            'fiscal_position': account_position_id,
            'date_invoice': context.get('date_inv') or today,
            'company_id': guia.company_id.id,
            'user_id': uid,
            'waybill_ids': [(4, guia.id)],
            'waybill_ref': guia.numero or ''
        }
        # Get all fields from OVD
        if guia.origin:
            invoice_vals['origin'] = invoice_vals[
                'origin'] + ': ' + guia.origin
        if guia.stock_picking_ids:
            if guia.stock_picking_ids[-1].sale_id:
                sale_id = guia.stock_picking_ids[-1].sale_id
                if sale_id.user_id:
                    invoice_vals['user_id'] = sale_id.user_id.id
                if sale_id.payment_term:
                    invoice_vals['payment_term'] = sale_id.payment_term.id
                if sale_id.partner_invoice_id:
                    invoice_vals['partner_id'] = sale_id.partner_invoice_id.id
                # fiscal position and account_id
                if sale_id.fiscal_position:
                    fpos = sale_id.fiscal_position
                    account_id = fpos_obj.map_account(
                        cr, uid, fpos, invoice_vals['account_id'])
                    invoice_vals.update(
                        {'account_id': account_id, 'fiscal_position': fpos.id})
            for pick in guia.stock_picking_ids:
                if pick.sale_id:
                    # client reference
                    if pick.sale_id.note:
                        invoice_vals['comment'] += u"\n" + pick.sale_id.note
                    # origin
                    if pick.sale_id.origin:
                        invoice_vals['origin'] += u':' + pick.sale_id.origin
        return invoice_vals

    def _prepare_invoice_line(self, cr, uid, group, line, invoice_id,
                              invoice_vals, context=None):
        """ Builds the dict containing the values for the invoice line
            @param group: True or False
            @param guia lines: lines from guia
            @return: dict that will be used to create the invoice line
        """
        fiscal_position = None
        invoice_obj = self.pool.get('account.invoice')
        invoice = invoice_obj.browse(cr, uid, invoice_id, context=context)
        # name
        if group:
            name = (line.guia_id.numero or '') + u'-' + line.name
        else:
            name = line.name
        if not line.product_id:
            return {
                'name': name,
                'sequence': line.sequence,
                'origin': line.guia_id.numero,
                'invoice_id': invoice_id,
                'state': 'text',
                'quantity': line.quantity,
                'waybill_reference': line.guia_id.numero,
                'waybill_date': line.guia_id.data_carga.split()[0],
                'type': invoice.type,
            }
        # account_id
        account_id = line.product_id.property_account_income.id
        if not account_id:
            product_category = line.product_id.categ_id
            account_id = product_category.property_account_income_categ.id
        if invoice_vals['fiscal_position']:
            fp_obj = self.pool.get('account.fiscal.position')
            fpos_id = invoice_vals['fiscal_position']
            fiscal_position = fp_obj.browse(cr, uid, fpos_id, context=context)
            account_id = fp_obj.map_account(
                cr, uid, fiscal_position, account_id)
        discount = 0.0
        price_unit = 0.0
        # taxes
        taxes = line.product_id.taxes_id
        if fiscal_position:
            taxes = fp_obj.map_tax(cr, uid, fiscal_position, taxes)
        else:
            taxes = map(lambda x: x.id, taxes)
        if line.move_line_id and line.move_line_id.sale_line_id:
            price_unit = line.move_line_id.sale_line_id.price_unit
            discount = line.move_line_id.sale_line_id.discount
        elif line.price_unit:
            price_unit = line.price_unit
        else:
            price_unit = line.product_id.list_price
        load_date = datetime.strptime(
            line.guia_id.data_carga, DEFAULT_SERVER_DATETIME_FORMAT)
        return {
            'name': name,
            'sequence': line.sequence,
            'invoice_id': invoice_id,
            'uos_id': line.uos_id.id,
            'product_id': line.product_id.id,
            'account_id': account_id,
            'price_unit': price_unit,
            'discount': discount or line.discount,
            'quantity': line.quantity,
            'invoice_line_tax_id': [(6, 0, taxes)],
            'account_analytic_id': line.account_analytic_id.id,
            'waybill_reference': line.guia_id.numero,
            'waybill_date': load_date.strftime(DEFAULT_SERVER_DATE_FORMAT),
            'type': invoice.type,
        }

    def action_close(self, cr, uid, ids, context=None):
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        self.write(cr, uid, ids, {'validation_date': now})
        return True

    def sync_guia_cancellation(self, cr, uid, ids, context=None):
        pass  # For certification services

    def action_cancel(self, cr, uid, ids, context=None):
        pick_obj = self.pool.get('stock.picking')
        for guia in self.browse(cr, uid, ids, context=context):
            if guia:
                if guia.invoice_state == 'invoiced' and guia.invoice_id:
                    if guia.invoice_id.state not in ('cancel', 'draft'):
                        raise osv.except_osv(
                            _('Error!'),
                            _('You can\'t cancel invoiced waybills'))
                self.sync_guia_cancellation(cr, uid, ids, context=context)
                self.write(cr, uid, ids, {'state': 'cancelada'})
                if guia.stock_picking_ids:
                    pick_ids = [pick.id for pick in guia.stock_picking_ids
                                if pick.waybill_state == 'waybilled']
                    waybill_state = {'waybill_state': 'none'}
                    pick_obj.write(cr, uid, pick_ids, waybill_state)
        return True


class account_linha_guia(osv.osv):
    _name = "account.linha.guia"
    _inherit = "account.invoice.line"
    _description = "Linha de Guia"

    def create(self, cr, user, vals, context=None):
        if not vals.get('product_id'):
            vals['quantity'] = 0
            vals['account_id'] = self._default_account(cr, user, None)
        return super(account_linha_guia, self).create(cr, user, vals, context)

    def product_id_change(self, cr, uid, ids, product, uom, qty=0, name='',
                          tipo='', partner_id=False, price_unit=False,
                          currency_id=False, company_id=None, context=None):
        if context is None:
            context = {}
        fpos_obj = self.pool.get('account.fiscal.position')
        partner_obj = self.pool.get('res.partner')
        product_obj = self.pool.get('product.product')
        account_obj = self.pool.get('account.account')
        company_obj = self.pool.get('res.company')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        if not company_id:
            company_id = context.get('company_id', False)
        context = dict(context)
        context.update({'company_id': company_id})
        if not partner_id:
            raise osv.except_osv(
                _('No Partner Defined !'),
                _("You must first select a partner !"))
        if not product:
            return {'value': {}, 'domain': {'product_uom': []}}
        part = partner_obj.browse(cr, uid, partner_id, context=context)

        if part.lang:
            context.update({'lang': part.lang})
        result = {}
        # Fiscal Position
        fpos = part.property_account_position

        # Price Unit
        res = product_obj.browse(cr, uid, product, context=context)
        result.update({'price_unit': res.list_price, 'name': res.name})

        # Account
        a = res.product_tmpl_id.property_account_income.id
        if not a:
            a = res.categ_id.property_account_income_categ.id
        result['account_id'] = a

        # Taxes
        if res.taxes_id:
            taxes = res.taxes_id
        elif a:
            taxes = account_obj.browse(cr, uid, a, context=context).tax_ids
        else:
            taxes = False
        if fpos and taxes:
            taxes = fpos_obj.map_tax(cr, uid, fpos, taxes)
        elif taxes:
            taxes = map(lambda x: x.id, taxes)
        result['invoice_line_tax_id'] = taxes

        domain = {}
        result['uos_id'] = res.uom_id.id or uom or False
        result['note'] = res.description
        if result['uos_id']:
            res2 = res.uom_id.category_id.id
            if res2:
                domain = {'uos_id': [('category_id', '=', res2)]}

        res_final = {'value': result, 'domain': domain}

        if not company_id or not currency_id:
            return res_final

        # Price Unit (currency and uom)
        company = company_obj.browse(cr, uid, company_id, context=context)
        currency = currency_obj.browse(cr, uid, currency_id, context=context)

        if company.currency_id.id != currency.id:
            new_price = res_final['value']['price_unit'] * currency.rate
            res_final['value']['price_unit'] = new_price

        if uom:
            uom = uom_obj.browse(cr, uid, uom, context=context)
            if res.uom_id.category_id.id == uom.category_id.id:
                new_price = res_final['value']['price_unit'] * uom.factor_inv
                res_final['value']['price_unit'] = new_price
        return res_final

    def uos_id_change(self, cr, uid, ids, product, uom, qty=0, name='',
                      tipo='', partner_id=False, price_unit=False,
                      currency_id=False, company_id=None, context=None):
        if context is None:
            context = {}
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        if not company_id:
            company_id = context.get('company_id', False)
        context = dict(context)
        context.update({'company_id': company_id})
        warning = {}
        res = self.product_id_change(
            cr, uid, ids, product, uom, qty, name, tipo, partner_id,
            price_unit, currency_id, context=context)
        if 'uos_id' in res['value']:
            del res['value']['uos_id']
        if not uom:
            res['value']['price_unit'] = 0.0
        if product and uom:
            prod = product_obj.browse(cr, uid, product, context=context)
            prod_uom = uom_obj.browse(cr, uid, uom, context=context)
            if prod.uom_id.category_id.id != prod_uom.category_id.id:
                warning = {
                    'title': _('Warning!'),
                    'message': _('You selected an Unit of Measure which '
                                 'is not compatible with the product.')
                }
            return {'value': res['value'], 'warning': warning}
        return res

    _columns = {
        'guia_id': fields.many2one(
            'account.guia', 'Referencia da Guia', ondelete='cascade',
            select=True),
        'account_id': fields.many2one(
            'account.account', 'Account',
            domain=[('type', '<>', 'view'), ('type', '<>', 'closed')],
            help="The income or expense account related to the selected "
                 "product."),
        'invoice_line_tax_id': fields.many2many(
            'account.tax', 'guia_line_tax', 'linha_guia_id', 'tax_id',
            'Impostos'),
        'company_id': fields.related(
            'guia_id', 'company_id', type='many2one', relation='res.company',
            string='Company', store=True, readonly=True),
        'state': fields.selection([
            ('article', 'Product'),
            ('title', 'Title'),
            ('text', 'Note'),
            ('subtotal', 'Sub Total'),
            ('line', 'Separator Line'),
            ('break', 'Page Break'), ], 'Type', select=True),
        'note': fields.text('Notes'),
        'move_line_id': fields.many2one('stock.move', 'Stock Move'),
        'purchase_line_id': fields.many2one(
            'purchase.order.line', 'Purchase Order Line'),
    }


class guias_por_dias(osv.osv):
    _name = "guias_por_dias"
    _description = "Guias por dias"
    _auto = False
    _rec_name = "dia"

    _columns = {
        "dia": fields.char("Dia", size=128, required=True),
        "total": fields.integer("Total", readonly=True),
    }

    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, "guias_por_dias")
        cr.execute("""
            CREATE or REPLACE view guias_por_dias as (
                SELECT
                    min(g.id) as id,
                    to_char(g.data_carga, 'YYYY-MM-DD') as dia,
                    COUNT(g.id) as total
                FROM
                    account_guia g
                GROUP BY
                    to_char(g.data_carga, 'YYYY-MM-DD')
            )
        """)


class license_plate(osv.osv):
    _name = "account.license_plate"
    _columns = {
        'name': fields.char('License Plate', size=32),
    }
