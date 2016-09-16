# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./

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
