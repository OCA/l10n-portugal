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

from openerp.osv import fields, osv


class hr_config_settings(osv.osv_memory):
    _name = 'hr.config.settings'
    _inherit = 'hr.config.settings'

    _columns = {
        'module_tko_hr_reports': fields.boolean("Allow to download generic "
                                                "payslip reports",
                                                help='Adds Anual Payslip '
                                                     'reports.'),
        'module_tko_hr_tax_returns': fields.boolean("Manage Tax Returns",
                                                    help='Adds several legal '
                                                         'reports such as SS '
                                                         'and IRS reports.'),
        'module_tko_hr_training': fields.boolean("Manage HR Training",
                                                 help='Installs module that '
                                                      'allows you to manage '
                                                      'course register.'),
        'group_adhoc_rules': fields.boolean('Allow adding adhoc salary rules '
                                            'to payslip',
                                            implied_group="tko_hr_pt."
                                                          "group_adhoc_rules"),
    }
