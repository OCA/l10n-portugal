# -*- coding: utf-8 -*-
# Copyright (C) ThinkOpen Solutions (<http://thinkopen.solutions>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from openerp.osv import fields, osv


class hr_holidays_status(osv.osv):
    _name = "hr.holidays.status"
    _inherit = "hr.holidays.status"

    _columns = {
        'code': fields.char('Code', size=64, readonly=False),
    }
