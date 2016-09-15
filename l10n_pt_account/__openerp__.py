# -*- coding: utf-8 -*-
{
    'name': 'Contabilidade PT',
    'version': '1.122',
    'author': 'ThinkOpen Solutions,Odoo Community Association (OCA)',
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
        
    * Allows you to import products, clients and invoices to saft
NOTE: This documents to be valid, need a certification from Portuguese Treasury, for that you must install and configure the tko_ics2_pt module, provided by Thinkopen Solutions.''',
    'website': 'http://www.thinkopen.solutions/',
    'init_xml': [],
    'depends': ['base',
                'account',
                'account_cancel',
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
                   'base_vat_view.xml',
                   'guia_view.xml',
                   'product_view.xml',
                   'data/account_data2.xml',
                   'data/simplified_invoice_client.xml',
                   'in_debit_note_sequence.xml',
                   'account_workflow.xml',
                   'wizard/stock_create_waybill.xml',
                   'wizard/waybill_invoice_view.xml',
                   'stock_view.xml',
                   'simplified_invoice_view.xml',
                   'sale_view.xml',
                   'account_config_view.xml',
                   'res_config_view.xml',
                   'wizard/sale_make_invoice_advance.xml',
                   'report/account_payment_report.xml',
                   'report/account_invoice_report_view.xml'
                   ],
    'demo_xml': [
                 ],
    'test': [],
    'installable': True,
    'application': True,
    'active': True,
}
