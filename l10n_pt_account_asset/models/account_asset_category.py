# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014- Sossia, Lda. (<http://www.sossia.pt>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
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

from openerp import models, fields, api


class AccountAssetCategory(models.Model):
    _inherit = 'account.asset.category'

    legal_rate_id = fields.Many2one(
        'account.asset.legal_rate',
        string='Legal Rate',)

    @api.onchange('legal_rate_id')
    def onchange_legal_rate(self):
        if self.legal_rate_id:
            self.method_time = 'year'
            self.method_period = 'year'
            self.prorata = True
            self.method_number = round(100 /
                                       self.legal_rate_id.depreciation_rate, 0)

    _defaults = {
        'prorata': True,
    }
