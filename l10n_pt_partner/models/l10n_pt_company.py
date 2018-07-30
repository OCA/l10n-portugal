# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2015- Sossia, Lda. (<http://www.sossia.pt>)
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


class ResCompany(models.Model):
    _inherit = "res.company"

    share_capital = fields.Integer(string='Share Capital')

    account_officer_vat = fields.Char(
        string='Accountant TIN',
        help='TIN of the certified accounting officer',
        select=True)

    _sql_constraints = [(
        'share_capital_positive',
        'CHECK (share_capital >= 0)',
        "The value of the field 'Share Capital' must be positive."
        )]

    @api.multi
    @api.constrains('account_officer_vat')
    def check_account_officer_vat(self):
        if self.account_officer_vat:
            vat_country, vat_number = self.env['res.partner']._split_vat(
                self.account_officer_vat)
            if not self.partner_id.simple_vat_check(vat_country, vat_number):
                raise ValidationError(
                    _('The value %s for the Accountant TIN does not '
                        'seem to be valid. \nNote: the expected format is '
                        '%s' % (self.account_officer_vat, 'PT123456789')))
