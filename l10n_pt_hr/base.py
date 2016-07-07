# -*- coding: utf-8 -*-
# Copyright (C) ThinkOpen Solutions (<http://thinkopen.solutions>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp


class res_company(osv.osv):
    _inherit = "res.company"

    payroll_precision = dp.get_precision('Payroll')
    _columns = {
        'identification_name': fields.char('Identification Name', size=64),
        'niss': fields.char('SS Identification', size=64),
        'nif': fields.related('vat', type='char', string='Tax Identification'),
        'establishment': fields.char('Name Establishment', size=64),
        'tax_code': fields.char('Tax Code', size=64),
        'company_ss_tax': fields.float('Company SS Tax',
                                       digits_compute=payroll_precision),
    }
