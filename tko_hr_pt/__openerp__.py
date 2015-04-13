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
{
    'name': 'Human Resources PT',
    'version': '1.064',
    'category': 'Human Resources',
    "sequence": 38,
    'complexity': "normal",
    'description': """
    """,
    'author':"ThinkOpen Solutions PT",
    'website':'http://www.thinkopensolutions.com/',
    'images': [],
    'depends': [
                'base','hr_payroll',
    ],
    'init_xml': [
    ],
    'update_xml': [
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
    'demo_xml': [
    ],
    'installable': True,
    'active': False,
    'application': False,
}

