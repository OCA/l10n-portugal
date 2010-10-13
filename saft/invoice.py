#! -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time

import netsvc
from osv import fields, osv, orm
import pooler
from tools.translate import _


SoftCertNr = '1'


class account_invoice(osv.osv):
    _inherit = "account.invoice"
    
    """ create
    Não é este o metodo a personalizar, a assinatura não aocntece no estado 'draft', 
    mas sim quando a factura é confirmada e é atribuido o numero.
    Não encontro no codigo de 'invoice.py' o metodo que confirma a factura.......
    
    def create(self, cr, uid, vals, context=None):
        try:
            res = super(account_invoice, self).create(cr, uid, vals, context)
            for inv_id, name in self.name_get(cr, uid, [res], context=context):
                message = _('Invoice ') + " '" + name + "' "+ _("is waiting for validation.")
                self.log(cr, uid, inv_id, message)
            return res
        except Exception, e:
            if '"journal_id" viol' in e.args[0]:
                raise orm.except_orm(_('Configuration Error!'),
                     _('There is no Accounting Journal of type Sale/Purchase defined!'))
            else:
                raise orm.except_orm(_('UnknownError'), str(e))

                
    Personalizar o metodo write, quando ou apos mudar o estado para 'open'
    A data relevante para o saft   é o 'write_date', porque a factura é criada sempre noestado 'draft' 
    e só é verdadeiramente uma factura, quando é confirmada
    """

    def write(self, cr, uid, ids, vals, context=None):
        #pass
        res = super(account_invoice, self).write(cr, uid, ids, vals, context=context)
        if 'state' in vals and vals['state'] == 'open':
            # ler os campos que sao objecto da assinatura
            
            # calcular a assinatura



