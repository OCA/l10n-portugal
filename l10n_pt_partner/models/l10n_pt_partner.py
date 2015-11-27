# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2014- Sossia, Lda. (<http://www.sossia.pt>)
#    Copyright (c) 2008 Spanish Localization Team
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp import api, models, fields, _
from openerp.exceptions import ValidationError


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    acc_country_id = fields.Many2one(
        comodel_name='res.country',
        string='Country',
        help='If the bank account is Portuguese, the account number '
             'will be validated and formatted accordingly.')

    def _calc_check_digits(self, bic, branch, account):
        """Compute NIB's check digits"""
        nib = bic + branch + account + "00"
        check_digits = 98 - (long(nib) % 97)
        return "%2d" % check_digits

    def _check_bank_account(self, account):
        number = ""
        for i in account:
            if i.isdigit():
                number += i
        if len(number) != 21:
            return 'invalid-size'
        bank = number[0:4]
        branch = number[4:8]
        account = number[8:19]
        check_digits = number[19:21]
        if check_digits != self._calc_check_digits(bank, branch, account):
            return 'invalid-cd'
        return '%s %s %s %s' % (bank, branch, account, check_digits)

    def _pretty_iban(self, iban_str):
        """return iban_str in groups of four characters separated
        by a single space"""
        res = []
        while iban_str:
            res.append(iban_str[:4])
            iban_str = iban_str[4:]
        return ' '.join(res)

    def onchange_bank_account(self, cr, uid, ids, account, country_id, state,
                              context=None):
        if account and country_id:
            country = self.pool.get('res.country').browse(cr, uid, country_id,
                                                          context=context)
            if country.code.upper() == 'PT':
                bank_obj = self.pool.get('res.bank')
                if state == 'bank':
                    account = account.replace(' ', '')
                    number = self._check_bank_account(account)
                    if number == 'invalid-size':
                        return {
                            'warning': {
                                'title': _('Warning'),
                                'message': _('Account number should have 21 '
                                             'digits.')
                            }
                        }
                    if number == 'invalid-cd':
                        return {
                            'warning': {
                                'title': _('Warning'),
                                'message': _('Invalid bank account.')
                            }
                        }
                    bank_ids = bank_obj.search(cr, uid,
                                               [('code', '=', number[:4])],
                                               context=context)
                    if bank_ids:
                        return {'value': {'acc_number': number,
                                          'bank': bank_ids[0]}}
                    else:
                        return {'value': {'acc_number': number}}
                elif state == 'iban':
                    partner_bank_obj = self.pool['res.partner.bank']
                    if partner_bank_obj.is_iban_valid(cr, uid, account,
                                                      context):
                        number = self._pretty_iban(account.replace(" ", ""))
                        bank_ids = bank_obj.search(
                            cr, uid, [('code', '=', number[5:9])],
                            context=context)
                        if bank_ids:
                            return {'value': {'acc_number': number,
                                              'bank': bank_ids[0]}}
                        else:
                            return {'value': {'acc_number': number}}
                    else:
                        return {'warning': {'title': _('Warning'),
                                'message': _('IBAN account is not valid')}}
        return {'value': {}}


class ResBank(models.Model):
    _inherit = 'res.bank'

    code = fields.Char('Code', size=64)
    lname = fields.Char('Long name', size=128)
    vat = fields.Char('TIN', size=32)
    website = fields.Char('Website', size=64)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    previous_vat = ''

    alias = fields.Char(
        string='Alias',
        help='Trade name or any other form of alternative name',
        size=128, select=True)

    self_billing = fields.Selection([
        ('sales', 'Sales'),
        ('purchases', 'Purchases'),
        ('both', 'Both')],
        string='Self Billing',
        default='',
        help='Indicate if the partner is under any kind of self '
             'billing agreement')

    invoice_copies = fields.Integer(
        string="No. of copies",
        default=0,
        help="Set the number of copies of invoices (or other legal documents)"
             " to print. A value of 1 means that a print job will output the"
             " original document plus one copy.")

    _sql_constraints = [
        ('invoice_copies_between_0_3',
         'CHECK (invoice_copies >= 0 and invoice_copies <= 3)',
         'The no. of invoice copies should be a number between 0 and 3!'),
    ]

    def name_search(self, cr, uid, name, args=None, operator='ilike',
                    context=None, limit=100):
        if not args:
            args = []
        partners = super(ResPartner, self).name_search(cr, uid, name, args,
                                                       operator, context,
                                                       limit)
        ids = [x[0] for x in partners]
        if name and len(ids) == 0:
            ids = self.search(cr, uid, [('alias', operator, name)] + args,
                              limit=limit, context=context)
        return self.name_get(cr, uid, ids, context=context)

    def vat_change(self, cr, uid, ids, value, context=None):
        result = super(ResPartner, self).vat_change(cr, uid, ids, value,
                                                    context=context)
        if value:
            result['value']['vat'] = value.upper()
        return result

    @api.multi
    def _get_posted_inv_count(self):
        """Get the number of posted invoices of a customer"""
        return self.env['account.invoice'].search_count([
            ('partner_id', '=', self.id),
            ('type', 'like', 'out_'),
            ('state', '!=', 'draft')])

    @api.multi
    @api.constrains('name')
    def _check_name_change(self):
        if self.customer:
            if self._get_posted_inv_count() > 0:
                raise ValidationError(_("You can't change the name of a "
                                        "customer who has posted invoices"))

    @api.multi
    @api.constrains('vat')
    def _check_vat_change(self):
        if self.customer:
            if self._get_posted_inv_count() > 0:
                raise ValidationError(_("You can't change the TIN of a "
                                        "customer who has posted invoices"))
