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

from openerp.tools.translate import _
from openerp.osv import fields, osv

class hr_holidays_status(osv.osv):
    _name = "hr.holidays.status"
    _inherit = "hr.holidays.status"
    
    _columns = {
        'code': fields.char('Code', size=64, readonly=False, required=True),
    }
    
