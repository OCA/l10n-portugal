# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 Thinkopen Solutions, Lda. All Rights Reserved
#    http://www.thinkopensolutions.com.
#    $Id$
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

from openerp import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    property_stock_account_client_return = fields.Many2one(
        comodel_name='account.account', company_dependent=True,
        string='Stock Client Return Account')
    property_stock_account_supplier_return = fields.Many2one(
        comodel_name='account.account', company_dependent=True,
        string='Stock Supplier Return Account')


class ProductCategory(models.Model):
    _inherit = 'product.category'

    property_stock_variation = fields.Many2one(
        comodel_name='account.account', string="Stock Variation Account",
        company_dependent=True,
        help='When real-time inventory valuation is enabled on a product, '
             'this account will hold the current value of the products.')
