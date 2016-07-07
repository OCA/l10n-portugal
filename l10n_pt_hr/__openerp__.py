# -*- coding: utf-8 -*-
# Copyright (C) ThinkOpen Solutions (<http://thinkopen.solutions>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'Human Resources PT Localisation',
    'version': '8.0.2.0.0',
    'category': 'Human Resources',
    'author': "ThinkOpen Solutions PT,Odoo Community Association (OCA)",
    'website': 'http://thinkopen.solutions/',
    'license': 'Other OSI approved licence',
    'depends': [
        'base', 'hr_payroll',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/hr_security.xml',
        'hr_payroll_sequence.xml',
        'hr_payroll_workflow.xml',
        'hr_payroll_pt_view.xml',
        'base_view.xml',
        'hr_config_settings_view.xml',
    ],
    'installable': True,
    'application': False,
}
