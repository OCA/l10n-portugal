#!/usr/bin/env python
# -*- coding: utf-8 -*-
##########################################################################
#
# Copyright (C) ThinkOpen Solutions (<http://thinkopen.solutions>).
# All Rights Reserved
#
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
##########################################################################
{
    'name': 'Human Resources PT',
    'version': '1.064',
    'category': 'Human Resources',
    "sequence": 38,
    'author': "ThinkOpen Solutions PT,Odoo Community Association (OCA)",
    'website': 'http://thinkopen.solutions/',
    'license': 'LGPL',
    'images': [],
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
    'test': [
    ],
    'installable': True,
    'application': False,
}
