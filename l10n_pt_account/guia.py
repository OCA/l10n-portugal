# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./

from openerp import api, fields, models, _
from openerp.exceptions import Warning

from openerp import tools
import openerp.addons.decimal_precision as dp

from datetime import datetime, date, timedelta

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
    # http://www.forma-te.com/mediateca/download-
    #  document/5855-como-calcular-os-feriados-moveis.html
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


def _end_of_today(*a):
    return datetime.now().strftime("%Y-%m-%d 22:59:59")


def match_state(state):
    return lambda self, cr, uid, obj, ctx=None: obj['state'] == state


class Guia(models.Model):
    _name = "account.guia"
    _rec_name = "numero"
    _description = "Guia"
    _order = "numero desc, data_carga desc"
    _inherit = ['mail.thread']  # To add message thread
    _track = {
        'type': {
        },
        'state': {
            'l10n_pt_account.mt_waybill_canceled': match_state('cancelada'),
            'l10n_pt_account.mt_waybill_validated': match_state('arquivada'),
        },
    }

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            address_id = self.partner_id.address_get(['delivery'])['delivery']
            if not address_id:
                return
            address = self.env['res.partner'].browse(address_id)
            self.local_entrega = address.street if address.street else ''
            if address.street2:
                self.local_entrega += ' ' + address.street2
            self.cidade_entrega = address.city if address.city else ''
            self.codigo_postal_entrega = address.zip if address.zip else ''

    @api.onchange('company_id')
    @api.multi
    def onchange_company_id(self):
        if self.company_id:
            company_partner = self.env[
                'res.partner'].browse(self.company_id.id)
            address_id = company_partner.address_get(['delivery'])['delivery']
            if not address_id:
                return
            address = self.env['res.partner'].browse(address_id)
            self.local_carga = address.street if address.street else ''
            if address.street2:
                self.local_carga += ' ' + address.street2
            self.cidade_carga = address.city if address.city else ''
            self.codigo_postal_carga = address.zip if address.zip else ''

    @api.model
    def _get_currency_id(self):
        user = self.env['res.users'].browse(self._uid)
        if user.company_id:
            return user.company_id.currency_id.id
        return self.env['res.currency'].search([('rate', '=', 1.0)]).id

    @api.model
    def _get_type(self):
        valmap = {
            'search_default_remessa': 'remessa',
            'search_default_transporte': 'transporte',
            'search_default_devolucao': 'devolucao'
        }
        for key, value in valmap.items():
            if key in self._context:
                return value

    @api.multi
    def _get_invoice_line(self):
        return self.mapped(lambda line: line.guia_id)

    @api.multi
    def _compute_amount_all(self):
        for guia in self:
            res = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0
            }
            for line in guia.linhas_guia:
                res['amount_untaxed'] += line.price_subtotal
            res['amount_total'] = res['amount_tax'] + res['amount_untaxed']
            guia.update(res)

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

    @api.multi
    def _compute_deadline(self):
        for waybill in self:
            if waybill.validation_date:
                validation_date = fields.Datetime.from_string(
                    waybill.validation_date).date()
                deadline = self.add_five_weekdays(validation_date)
            else:
                deadline = date.today()
            waybill.invoice_deadline = fields.Date.to_string(deadline)

    @api.multi
    def _compute_overdue(self):
        for waybill in self:
            deadline = fields.Date.from_string(waybill.invoice_deadline)
            waybill.days_to_invoice = (deadline - date.today()).days

    READONLY_CANCELLED_OR_CONFIRMED = {
        'cancelada': [('readonly', True)],
        'arquivada': [('readonly', True)],
    }

    @api.model
    def _get_default_company_id(self):
        return self.env['res.company']._company_default_get('account.guia')

    numero = fields.Char('Numero', readonly=True, size=64)
    tipo = fields.Selection(selection=[
        ('remessa', 'Remessa'),
        ('transporte', 'Transporte'),
        ('devolucao', 'Devolu\xc3\xa7\xc3\xa3o')],
        string='Tipo de Guia', states={
            'cancelada': [('readonly', True)],
            'arquivada': [('readonly', True)],
        }, required=True, index=True, default=_get_type)
    state = fields.Selection(
        [('aberta', 'Aberta'),
         ('arquivada', 'Arquivada'),
         ('cancelada', 'Cancelada')],
        string='Estado', readonly=True, required=True,
        index=True, default='aberta')
    data_carga = fields.Datetime(
        string='Data de Carga', states=READONLY_CANCELLED_OR_CONFIRMED,
        required=True, index=True, default=fields.Datetime.now)
    data_descarga = fields.Datetime(
        string='Data da Descarga', states=READONLY_CANCELLED_OR_CONFIRMED,
        index=True, default=_end_of_today)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente',
        states=READONLY_CANCELLED_OR_CONFIRMED,
        required=True)
    local_carga = fields.Char(
        string='Local de Carga', states=READONLY_CANCELLED_OR_CONFIRMED,
        index=True, size=64, default=u"N/ Armazém")
    local_entrega = fields.Char(
        string='Local de Descarga', states=READONLY_CANCELLED_OR_CONFIRMED,
        index=True, size=64, default=u"Morada Cliente")
    cidade_carga = fields.Char(
        string='Cidade de Carga', states=READONLY_CANCELLED_OR_CONFIRMED,
        index=True, size=64)
    cidade_entrega = fields.Char(
        string='Cidade de Descarga', states=READONLY_CANCELLED_OR_CONFIRMED,
        index=True, size=64)
    codigo_postal_carga = fields.Char(
        string='Codigo Postal de Carga',
        states=READONLY_CANCELLED_OR_CONFIRMED,
        index=True, size=64)
    codigo_postal_entrega = fields.Char(
        string='Codigo Postal de Descarga',
        states=READONLY_CANCELLED_OR_CONFIRMED, index=True, size=64)
    matricula = fields.Many2one(
        'account.license_plate', string=u'Matrícula',
        states=READONLY_CANCELLED_OR_CONFIRMED, index=True)
    linhas_guia = fields.One2many(
        'account.linha.guia', 'guia_id', string='Linhas Guia',
        states=READONLY_CANCELLED_OR_CONFIRMED)
    company_id = fields.Many2one(
        'res.company', string='Company', readonly=True,
        required=True, change_default=True, default=_get_default_company_id)
    observacoes = fields.Text(string=u'Descrição')
    currency_id = fields.Many2one(
        'res.currency', string='Currency', readonly=True,
        required=True, default=_get_currency_id)
    stock_picking_ids = fields.One2many(
        'stock.picking', 'waybill_id', string='Pickings')
    sale_id = fields.Many2one('sale.order', string='Ordem de Venda')
    invoice_id = fields.Many2one('account.invoice', string='Fatura')
    invoice_state = fields.Selection(
        [('none', u'Não Faturado'), ('invoiced', 'Faturado')],
        string=u'Faturação', readonly=True, default='none')
    origin = fields.Char(
        string='Origem', states=READONLY_CANCELLED_OR_CONFIRMED,
        help=u'Referência ao documento que deu origem à guia.',
        select=True, size=128)
    user_id = fields.Many2one(
        'res.users', string='User', states=READONLY_CANCELLED_OR_CONFIRMED,
        readonly=True, default=lambda self: self._uid)
    name = fields.Char(
        string='Client Reference', states=READONLY_CANCELLED_OR_CONFIRMED,
        size=128)
    amount_untaxed = fields.Float(
        compute='_compute_amount_all', multi='all', store=True,
        track_visibility='always', string='Subtotal',
        digits_compute=dp.get_precision('Account'))
    amount_tax = fields.Float(
        compute='_compute_amount_all', multi='all',
        store=True, string='Tax',
        digits_compute=dp.get_precision('Account'))
    amount_total = fields.Float(
        compute='_compute_amount_all', multi='all',
        store=True, string='Total',
        digits_compute=dp.get_precision('Account'))
    validation_date = fields.Datetime(string='Date of validation')
    days_to_invoice = fields.Integer(
        compute='_compute_overdue', string='Days to invoice',
        help='Number of days to invoice the waybill')
    invoice_deadline = fields.Date(
        compute='_compute_deadline', string='Deadline',
        help='Deadline to invoice the waybill')

    @api.multi
    def unlink(self):
        if any(guia.state == 'aberta' for guia in self):
            raise Warning(_('It\'s not possible to delete archived waybills!'))
        return super(Guia, self).unlink()

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        default.update({
            'numero': False,
            'invoice_state': 'none',
            'invoice_id': False,
            'stock_picking_ids': False,
            'sale_id': False,
        })
        return super(Guia, self).copy(cr, uid, id, default, context)

    @api.multi
    def _prepare_invoice_group(self, partner, invoice):
        """ Builds the dict for grouped invoices
            @param picking: picking object
            @param partner: object of the partner to invoice
                            (not used here, but may be usefull if
                            this function is inherited)
            @param invoice: object of the invoice that we are updating
            @return: dict that will be used to update the invoice
        """
        def join_valid(s, x):
            return s.join(filter(None, x))
        guia = self
        invoice_vals = {
            'name': join_valid(', ', (invoice.name, guia.name)),
            'origin': join_valid(', ', (invoice.origin,
                                        guia.numero,
                                        guia.origin)),
            'comment': join_valid('\n', (invoice.comment, guia.numero)),
            'date_invoice': self.env.context.get('date_inv', False),
            'user_id': self.env.uid,
            'waybill_ids': [(4, guia.id)],
            'waybill_ref': join_valid(', ', (guia.numero,
                                             invoice.waybill_ref)),
        }
        for pick in guia.stock_picking_ids:
            if not pick.sale_id:
                continue
            if pick.sale_id.client_order_ref:
                invoice_vals['name'] = pick.sale_id.client_order_ref\
                    + ', ' + invoice_vals['name']
            if pick.sale_id.note:
                invoice_vals['comment'] += "\n" + pick.sale_id.note
            if pick.sale_id.origin:
                invoice_vals['origin'] += ': ' + pick.sale_id.origin
        return invoice_vals

    @api.multi
    def action_invoice_onguia(self):
        inv_obj = self.env['account.invoice']
        obj_invoice_line = self.env['account.invoice.line']
        picking_obj = self.env['stock.picking']
        invoices_group = {}
        invoices = inv_obj.browse()
        inv_type = self._context.get('type', False)
        group = self._context.get('group', False)
        if not inv_type:
            raise Warning(_('Tipo de Fatura'))
        for guia in self:
            partner = guia.partner_id
            if partner.parent_id and not partner.is_company:
                partner = partner.parent_id
            if (guia.state != 'arquivada' or guia.invoice_state != 'none' or
                    guia.tipo not in ('remessa', 'transporte')):
                continue
            if group and partner in invoices_group:
                invoice = invoices_group[partner]
                invoice_vals_group = guia._prepare_invoice_group(
                    partner, invoice)
                invoice.write(invoice_vals_group)
            else:
                # create invoice
                invoice_vals = guia._prepare_invoice(partner)
                invoice = inv_obj.create(invoice_vals)
                invoices |= invoice
                invoices_group[partner] = invoice

            if guia.stock_picking_ids:
                for picking in guia.stock_picking_ids:
                    picking_obj._invoice_hook(picking, invoice.id)
            # create invoice lines
            for line in guia.linhas_guia:
                vals = line._prepare_invoice_line(group, invoice)
                if vals:
                    obj_invoice_line.create(vals)

            guia.invoice_id = invoice.id
            # write invoice in related pickings
            if guia.stock_picking_ids:
                uninvoiced_picks = guia.stock_picking_ids.filtered(
                    lambda p: p.invoice_state not in ('invoiced', 'none'))
                uninvoiced_picks.write({'invoice_state': 'invoiced'})
        action = {}
        data_pool = self.env['ir.model.data']
        if inv_type == 'out_invoice':
            action_obj = data_pool.xmlid_to_object(
                'account.action_invoice_tree1')
        elif inv_type == 'simplified_invoice':
            action_obj = data_pool.xmlid_to_object(
                'l10n_pt_account.action_simplified_invoice_tree')
        if action_obj:
            action = action_obj.read([])[0]
            action['domain'] = str([('id', 'in', invoices.ids)])
        return action

    @api.multi
    def _prepare_invoice(self, partner):
        """Prepare the dict of values to create the new invoice for a
           waybill.

           :param browse_record guia: guia record to invoice
           :param list(int) line: list of invoice line IDs that must be
                                  attached to the invoice
           :return: dict of value to create() the invoice
        """
        guia = self
        journal = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', guia.company_id.id)],
            limit=1)
        if not journal:
            msg = _('There is no sales journal defined '
                    'for this company: "%s" (id: %d)')
            raise Warning(msg % (guia.company_id.name, guia.company_id.id))
        inv_type = self._context.get('type', False)
        if not inv_type:
            raise Warning(_('Tipo de Fatura'))
        partner_addr = partner.address_get(['invoice'])
        account = partner.property_account_receivable_id
        term = partner.property_payment_term_id
        fposition = partner.property_account_position_id
        date_invoice = self._context.get('date_inv', fields.Date.today())
        invoice_vals = {
            'name': guia.name or '',
            'origin': guia.numero or '',
            'type': inv_type,
            'reference': guia.numero or '',
            'account_id': account.id,
            'partner_id': partner_addr['invoice'] or partner.id,
            'journal_id': journal.id,
            'currency_id': guia.currency_id and guia.currency_id.id or False,
            'comment': guia.numero or '',
            'payment_term_id': term.id if term else False,
            'fiscal_position_id': fposition.id if fposition else False,
            'date_invoice': date_invoice,
            'company_id': guia.company_id.id,
            'user_id': self._uid,
            'waybill_ids': [(4, guia.id)],
            'waybill_ref': guia.numero or ''
        }
        # Get all fields from OVD
        if guia.origin:
            invoice_vals['origin'] += u': ' + guia.origin
        if guia.stock_picking_ids:
            if guia.stock_picking_ids[-1].sale_id:
                sale = guia.stock_picking_ids[-1].sale_id
                # user_id, # payment_term # partner
                if sale.user_id:
                    invoice_vals['user_id'] = sale.user_id.id
                if sale.payment_term:
                    invoice_vals['payment_term_id'] = sale.payment_term.id
                if sale.partner_invoice_id:
                    invoice_vals['partner_id'] = sale.partner_invoice_id.id
                # fiscal position and account
                if sale.fiscal_position_id:
                    account = sale.fiscal_position_id.map_account(account)
                    invoice_vals.update({
                        'account_id': account.id,
                        'fiscal_position_id': sale.fiscal_position_id.id,
                    })
            for pick in guia.stock_picking_ids:
                if not pick.sale_id:
                    continue
                # notes
                invoice_vals['comment'] += u"\n" + (pick.sale_id.note or '')
                # origin
                invoice_vals['origin'] += u':' + (pick.sale_id.origin or '')
        return invoice_vals

    @api.multi
    def action_close(self):
        self.write(
            {'validation_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        return True

    @api.multi
    def sync_guia_cancellation(self):
        pass  # For certification services

    @api.multi
    def action_cancel(self):
        for guia in self:
            if (guia.invoice_state == 'invoiced' and guia.invoice_id and
                    guia.invoice_id.state not in ('cancel', 'draft')):
                raise Warning(u'Não pode cancelar guias faturadas.')
        self.sync_guia_cancellation()
        self.write({'state': 'cancelada'})
        waybilled_picks = guia.stock_picking_ids.filtered(
            lambda p: p.waybill_state == 'waybilled')
        waybilled_picks.write({'waybill_state': 'none'})
        return True


class LinhaGuia(models.Model):
    _name = "account.linha.guia"
    _inherit = "account.invoice.line"
    _description = "Linha de Guia"

    @api.model
    def create(self, vals):
        if 'product_id' in vals and not vals['product_id']:
            vals['quantity'] = 0
            vals['account_id'] = self._default_account()
        return super(LinhaGuia, self).create(vals)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.guia_id.partner_id:
            raise Warning(_("You must first select a partner !"))
        if not self.product_id:
            return {'domain': {'product_uom': []}}

        # Fiscal Position
        fpos = self.guia_id.partner_id.property_account_position_id

        # Price Unit
        self.price_unit = self.product_id.list_price
        self.name = self.product_id.name

        # Account
        a = self.product_id.product_tmpl_id.property_account_income_id
        if not a:
            a = self.product_id.categ_id.property_account_income_categ_id
        self.account_id = a

        # Taxes
        taxes = self.product_id.taxes_id or (a and a.tax_ids) or False
        if fpos and taxes:
            taxes = fpos.map_tax(taxes)
        self.invoice_line_tax_id = taxes

        domain = {}
        self.uom_id = self.product_id.uom_id or False
        self.note = self.product_id.description
        if self.uom_id and self.product_id.uom_id.category_id:
            uom_category = self.product_id.uom_id.category_id
            domain = {'uom_id': [('category_id', '=', uom_category.id)]}

        res_final = {'domain': domain}

        if not self.guia_id.company_id or not self.guia_id.currency_id:
            return res_final

        # Price Unit (currency and uom)
        if self.guia_id.company_id.currency_id != self.guia_id.currency_id:
            self.price_unit *= self.currency_id.rate

        if self.uom_id:
            if self.product_id.uom_id.category_id == self.uom_id.category_id:
                self.price_unit *= self.uom_id.factor_inv

        return res_final

    @api.onchange('uom_id')
    def uom_id_change(self):
        if (self.product_id and self.uom_id and
                self.product_id.uom_id.category_id != self.uom_id.category_id):
            warning = {
                'title': _('Warning!'),
                'message': _('You selected an Unit of Measure which '
                             'is not compatible with the product.')
            }
            return {'warning': warning}

    guia_id = fields.Many2one(
        'account.guia', string='Referencia da Guia', ondelete='cascade',
        index=True)
    account_id = fields.Many2one(
        'account.account', string='Account',
        domain=[('type', '!=', 'view'), ('type', '!=', 'closed')],
        help='The income or expense account related to the selected product.')
    invoice_line_tax_id = fields.Many2many(
        'account.tax', 'guia_line_tax', 'linha_guia_id', 'tax_id',
        string='Impostos')
    company_id = fields.Many2one(
        'res.company', related='guia_id.company_id', readonly=True,
        string='Company', store=True)
    state = fields.Selection(selection=[
        ('article', 'Product'),
        ('title', 'Title'),
        ('text', 'Note'),
        ('subtotal', 'Sub Total'),
        ('line', 'Separator Line'),
        ('break', 'Page Break')],
        string='Type', index=True)
    note = fields.Text('Notes')
    move_line_id = fields.Many2one('stock.move', string='Stock Move')
    purchase_line_id = fields.Many2one(
        'purchase.order.line', string='Purchase Order Line')

    @api.multi
    def _prepare_invoice_line(self, group, invoice):
        """ Builds the dict containing the values for the invoice line
            @param group: True or False
            @param guia lines: lines from guia
            @return: dict that will be used to create the invoice line
        """
        line = self
        # name
        if group:
            name = u'-'.join(filter(None, (line.guia_id.numero, line.name)))
        else:
            name = line.name
        # origin
        origin = line.name
        if (line.move_line_id and line.move_line_id.picking_id and
                line.move_line_id.picking_id.origin):
            origin += ':' + line.move_line_id.picking_id.origin
        load_datetime = fields.Datetime.from_string(line.guia_id.data_carga)
        load_date = fields.Date.to_string(load_datetime.date())
        if not line.product_id:
            return {
                'name': name,
                'sequence': line.sequence or False,
                'origin': line.guia_id.numero,
                'invoice_id': invoice.id,
                'state': 'text',
                'quantity': line.quantity,
                'waybill_reference': line.guia_id.numero,
                'waybill_date': load_date,
                'type': invoice.type,
            }
        # account
        account = line.product_id.property_account_income_id
        if not account:
            account = line.product_id.categ_id.property_account_income_categ_id
        if invoice.fiscal_position_id:
            account = invoice.fiscal_position_id.map_account(account)
        # taxes
        taxes = line.product_id.taxes_id
        if invoice.fiscal_position_id:
            taxes = invoice.fiscal_position_id.map_tax(taxes)
        if line.price_unit:
            price_unit = line.price_unit
        else:
            price_unit = line.product_id.list_price
        return {
            'name': name,
            'origin': origin,
            'sequence': line.sequence,
            'invoice_id': invoice.id,
            'uom_id': line.uom_id.id if line.uom_id else False,
            'product_id': line.product_id.id,
            'account_id': account.id,
            'price_unit': price_unit,
            'discount': line.discount,
            'quantity': line.quantity,
            'invoice_line_tax_id': [(6, 0, taxes)],
            'account_analytic_id': line.account_analytic_id.id,
            'waybill_reference': line.guia_id.numero,
            'waybill_date': load_date,
            'type': invoice.type,
        }


class GuiasPorDia(models.Model):
    _name = "guias_por_dias"
    _description = "Guias por dias"
    _auto = False
    _rec_name = "dia"

    dia = fields.Char(string='Dia', size=128, required=True)
    total = fields.Integer(string='Total', readonly=True)

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


class LicensePlate(models.Model):
    _name = "account.license_plate"

    name = fields.Char(string='License Plate', size=32)
