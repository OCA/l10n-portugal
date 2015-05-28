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

from openerp.osv import osv
from openerp.osv import fields
from openerp.tools.translate import _


class product_template(osv.osv):
    _name = 'product.template'
    _inherit = 'product.template'
    _columns = {
        'property_stock_account_client_return': fields.property(
            type='many2one', relation='account.account',
            string='Stock Client Return Account', method=True, view_load=True),
        'property_stock_account_supplier_return': fields.property(
            type='many2one', relation='account.account',
            string='Stock Supplier Return Account', method=True,
            view_load=True),
    }


class product_category(osv.osv):
    _inherit = 'product.category'
    _columns = {
        'property_stock_variation': fields.property(
            type='many2one',
            relation='account.account',
            string="Stock Variation Account",
            method=True, view_load=True,
            help="When real-time inventory valuation is enabled on a product, "
            "this account will hold the current value of the products."),
    }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
