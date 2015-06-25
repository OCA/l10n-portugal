# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014- Sossia, Lda. (<http://www.sossia.pt>)
#    Copyright (C) 2012 Serv. Tecnol. Avanzados (http://www.serviciosbaeza.com)
#                       Pedro Manuel Baeza <pedro.baeza@serviciosbaeza.com>
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

    method_time = fields.Selection(
        string='Time Method',
        selection=[('number', 'Number of Depreciations'),
                   ('end', 'Ending Date'),
                   ('percentage', 'Fixed percentage')],
        default='percentage',
        required=True,
        help="Choose the method to use to compute the dates and number of "
        "depreciation lines.\n"
        "  * Number of Depreciations: Fix the number of depreciation "
        "lines and the time between 2 depreciations.\n"
        "  * Ending Date: Choose the time between 2 depreciations "
        "and the date the depreciations won't go beyond.\n"
        "  * Fixed percentage: Choose the time between 2 "
        "depreciations and the percentage to depreciate.")

    depreciation_rate = fields.Float(
        string='Depreciation rate (%)',
        default=100.0,
        digits=(3, 2))

    move_end_period = fields.Boolean(
        string='At the end of the period',
        default=True,
        help="Check if you wish to set the date of your depreciation"
        " entries at the end of the period.")

    legal_rate_id = fields.Many2one(
        'account.asset.legal_rate',
        string='Legal Rate',
        help="Default legal rate. It will be copied to the asset"
        " form on creation but can be modified afterwards")

    _sql_constraints = [
        ('depreciation_rate',
         ' CHECK (depreciation_rate > 0 and depreciation_rate <= 100)',
         'Invalid percentage!'),
    ]

    @api.onchange('legal_rate_id')
    def onchange_legal_rate(self):
        if self.legal_rate_id:
            self.method = 'linear'
            self.prorata = True
            self.move_end_period = True
            self.method_time = 'percentage'
            self.method_period = 12
            self.depreciation_rate = self.legal_rate_id.depreciation_rate
