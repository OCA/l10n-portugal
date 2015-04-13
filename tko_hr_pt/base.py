#!/usr/bin/env python
# coding: utf-8
########################################################################################
#
# Copyright (C) ThinkOpen Solutions (<http://thinkopen.solutions>). All Rights Reserved
# Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3.0 of the License, or (at your option) any later version.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library.
#
########################################################################################


from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp

class res_company(osv.osv):
    _inherit = "res.company"

    _columns = {
                'identification_name': fields.char('Identification Name', size=64),
                'niss': fields.char('SS Identification', size=64),
                'nif': fields.char('Tax Identification', size=64),
                'establishment': fields.char('Name Establishment', size=64),
                'tax_code': fields.char('Tax Code', size=64),
                'company_ss_tax' : fields.float('Company SS Tax',digits_compute=dp.get_precision('Payroll')),
                }
    
