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

from saft import SoftCertNr 


class account_invoice(osv.osv):
    _inherit = "account.invoice"
    
    """ 
    Não é o metodo 'create' a personalizar, a assinatura não aocntece no estado 'draft', 
    mas sim quando a factura é confirmada e é atribuido o numero.
                
    Personalizar o metodo write, quando ou apos mudar o estado para 'open'
    A data relevante para o saft   é o 'write_date', porque a factura é criada sempre no estado 'draft' 
    e só é verdadeiramente uma factura, quando é confirmada
    """

    def write(self, cr, uid, ids, vals, context=None):
        #pass
        res = super(account_invoice, self).write(cr, uid, ids, vals, context=context)
        if 'state' in vals and vals['state'] == 'open':
            # ler os campos que sao objecto da assinatura
            
            # calcular a assinatura

            # Gravar a assinatura na BD
            cr.execute("UPDATE account_invoice SET hash = " + signature
            + " WHERE id = " + str(id) )


