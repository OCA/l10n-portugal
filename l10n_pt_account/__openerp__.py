# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Tiny SPRL (<http://tiny.be>).
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
    'author': 'ThinkOpen Solutions',
    'category' : 'Accounting & Finance',
    'sequence': 1,
    'license' : 'LGPL-3',
    'description': '''Customization of Accounting for Portugal.
This module implements several Portuguese specific accounting documents:
    Documents:
        * Debit Notes; 
        * Credit Notes;
        * Supplier Debit Notes;
        * All Waybill Types.
        
    Reports:
        * Voucher Print
        
    * Allows you to import products, clients and invoices to saft
NOTE: This documents to be valid, need a certification from Portuguese Treasury, for that you must install and configure the tko_ics2_pt module, provided by Thinkopen Solutions.''',
    'website': 'http://www.thinkopen.solutions/',
    'init_xml': [],
    'depends': ['base',
                'account',
                'account_cancel',
                'account_voucher',
                'purchase',
                'sale',
                'stock',
                'stock_account',
                'l10n_pt'
                ],
    'update_xml': [
                   'security/account_security.xml',
                   'security/ir.model.access.csv',
                   'account_invoice_view.xml',
                   'account_view.xml',
                   'guia_view.xml',
                   'product_view.xml',
                   #'wizard/account_invoice_refund_view.xml',
                   'account_guia_report.xml',
                   #'account_voucher_report.xml',
                   'data/account_data2.xml',
                   'data/simplified_invoice_client.xml',
                   'in_debit_note_sequence.xml',
                   'account_workflow.xml',
                   'wizard/stock_create_waybill.xml',
                   #'wizard/stock_simplified_invoice_onshipping_view.xml',
                   'wizard/waybill_invoice_view.xml',
                   'stock_view.xml',
                   'simplified_invoice_view.xml',
                   'sale_view.xml',
                   'account_config_view.xml',
                   'res_config_view.xml',
                   'wizard/sale_make_invoice_advance.xml',
                   ],
    'demo_xml': [
                 #'demo/account_minimal.xml',
                 ],
    'test': [],
    'installable': True,
    'application': True,
    'active': True,
    #'certificate': '',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
