# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from openerp.report import report_sxw

import time


class AccountGuia(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(AccountGuia, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
        })

report_sxw.report_sxw(
    'report.account.guia',
    'account.guia',
    'report/account_guia.rml',
    parser=AccountGuia
)
