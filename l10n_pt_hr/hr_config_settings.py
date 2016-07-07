# -*- coding: utf-8 -*-
# Copyright (C) ThinkOpen Solutions (<http://thinkopen.solutions>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

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
