# -*- coding: utf-8 -*-
##############################################################################
#
#    Thinkopen - Portugal & Brasil
#    Copyright (C) Thinkopen Solutions (<http://www.thinkopensolutions.com>).
#
#    $Id$
#
#    This module was developed by ThinkOpen Solutions for OpenERP as a
#    contribution to the community.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version $revnoof the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'Contabilidade PT',
    'version': '1.122',
    'author': 'ThinkOpen Solutions,Odoo Community Association (OCA)',
    'license': 'Other OSI approved licence',
    'category': 'Generic Modules/Accounting',
    'website': 'http://thinkopen.solutions/',
    'depends': ['base',
                'account',
                'account_cancel',
                'purchase',
                'sale',
                'stock',
                'stock_account',
                ],
    'data': [
        'security/account_security.xml',
        'security/ir.model.access.csv',
        'account_invoice_view.xml',
        'account_view.xml',
        'guia_view.xml',
        'product_view.xml',
        'account_guia_report.xml',
        'account_voucher_report.xml',
        'data/account_data2.xml',
        'data/simplified_invoice_client.xml',
        'in_debit_note_sequence.xml',
        'account_workflow.xml',
        'wizard/stock_create_waybill.xml',
        'wizard/stock_simplified_invoice_onshipping_view.xml',
        'wizard/waybill_invoice_view.xml',
        'stock_view.xml',
        'simplified_invoice_view.xml',
        'sale_view.xml',
        'account_config_view.xml',
        'res_config_view.xml',
    ],
    'test': [],
    'installable': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
