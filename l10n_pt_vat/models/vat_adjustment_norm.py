# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2014- Sossia, Lda. (<http://www.sossia.pt>)
#    Copyright (C) 2004 OpenERP SA (<http://www.odoo.com>)
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

from openerp import models, fields


class AccountVATAdjustmentNorm(models.Model):
    "Support fields 40/41 of the VAT Statement)"

    _name = "account.vat.adjustment_norm"
    _description = "VAT Adjustment Norm"

    name = fields.Char(
        string='Name',
        required=True)

    active = fields.Boolean(
        string='Active',
        default=True,
        help="If the active field is set to False, it "
             "will allow you to hide the adjustment norm without removing it.")

    note = fields.Text(
        string='Description',
        translate=True)

    out_refunds = fields.Boolean(
        string='Use on company refunds',
        help="If True, it will allow you to apply the adjustment "
             "norm to your company refunds.")

    in_refunds = fields.Boolean(
        string='Use on third party refunds',
        help="If True, it will allow you to apply the adjustment "
             "norm to third party companies refunds.")
