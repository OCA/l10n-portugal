# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 Thinkopen Solutions, Lda. All Rights Reserved
#    http://www.thinkopensolutions.com.
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time
from openerp.report import report_sxw
import amount_to_text_pt
from openerp.osv.orm import browse_null
from openerp.osv import osv
from openerp.tools.translate import _

class report_voucher_print(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(report_voucher_print, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'time': time,
            'get_title': self.get_title,
            'convert':self.convert,
            'get_writeoff':self.get_writeoff,
            'get_total_writeoff':self.get_total_writeoff,
            'get_total':self.get_total,
            'adr_get':self._adr_get,
            'get_line':self.get_line,
        })
        self.context = context

    def convert(self, voucher, cur):
        total = voucher.amount
        amt_en = amount_to_text_pt.amount_to_text(total, 'pt', cur)
        return amt_en
            
    def get_total(self,voucher):
        result = 0.0
        if voucher.type in ('receipt','sale'):
            list = voucher.line_cr_ids
        else:
            list = voucher.line_dr_ids
        for line in list:
            result += line.amount
        return result

    def get_total_writeoff(self, voucher):
        result  = 0.0
        if voucher.payment_option == 'with_writeoff':
            debit = credit = 0.0
            for l in voucher.line_dr_ids:
                debit += l.amount
            for l in voucher.line_cr_ids:
                credit += l.amount
            if voucher.type in ('receipt','sale'):
                result =  abs(voucher.amount - abs(credit - debit))
            else:
                result =  abs(voucher.amount - abs(debit - credit))
        return result
    
    def get_writeoff(self,line_ids):
        result = 0.0
        result = abs(line_ids.amount_original - line_ids.amount)
        return result

    def get_title(self, type):
        if type in ('receipt','sale'):
            title = _("Recibo")
        else:
            title = _("Nota de pagamento")
        return title
    def get_line(self, voucher):
        result= []
        if voucher.type in ('receipt','sale'):
            list_cr = voucher.line_cr_ids
            list_dr = voucher.line_dr_ids
        else:
            list_cr = voucher.line_dr_ids
            list_dr = voucher.line_cr_ids
        
        for line in list_cr:
            res={}
            if line.amount > 0.0:
                if line.move_line_id.move_id:
                    res['name'] = line.move_line_id.move_id.name or ''
                    if voucher.type == 'payment':
                        res['name'] = line.move_line_id.move_id.name + ' (' + line.move_line_id.move_id.ref + ')'
                else:
                    res['name'] = " "
                if 'af' in res['name']:
                    res['type'] = 'N/Saldo'
                else:
                    res['type'] = 'N/Factura'
                res['date_original'] = line.date_original or ''
                res['amount_original'] = line.amount_original
                res['amount_unreconciled'] = line.amount_unreconciled - line.amount 
                res['amount'] = line.amount 
                result.append(res)
        for line in list_dr:
            res={}
            if line.amount > 0.0:
                if line.move_line_id.move_id:
                    res['name'] = line.move_line_id.move_id.name or ''
                    if voucher.type == 'payment':
                        res['name'] = line.move_line_id.move_id.name + ' (' + line.move_line_id.move_id.ref + ')'
                else:
                    res['name'] = " "
                if 'af' in res['name']:
                    res['type'] = 'N/Saldo'
                else:
                    res['type'] = 'N/Lanç.Crédito'
                res['date_original'] = line.date_original or ''
                res['amount_original'] = line.amount_original
                res['amount_unreconciled'] = line.amount_unreconciled - line.amount 
                res['amount'] = line.amount
                result.append(res)
        return result

    def _adr_get(self, voucher):
        res = {}
        res_partner = self.pool.get('res.partner')
        result = {
                  'street': '',
                  'street2': '',
                  'city': '',
                  'zip': '',
                  'country_id':'',
                  'state_id':'',
                 }
        addresses = res_partner.address_get(self.cr, self.uid, [voucher.partner_id.id], ['invoice'])
        addr_id = addresses and addresses['invoice'] or False
        ctx = {'lang': u'pt_PT'}
        if addr_id:
            result = res_partner.read(self.cr, self.uid, addr_id, ['street', 'street2', 'city', 'zip', 'country_id', 'state_id'], ctx)
        else:
            raise osv.except_osv(_('Erro !'), _('Configure a morada do parceiro!'))
        return result

report_sxw.report_sxw(
    'report.tko.voucher.print',
    'account.voucher',
    'addons-tko/tko_acount_pt/report/account_voucher_print.rml',
    parser=report_voucher_print,header=True
)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
