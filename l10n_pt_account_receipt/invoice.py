# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    
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
from osv import fields, osv
import ir
import pooler
import mx.DateTime
from mx.DateTime import RelativeDateTime
from tools import config
from tools.translate import _


class account_invoice(osv.osv):
    """Tentativa de ultrapassar o bug no valor residual das facturas quando sujeitas a reconciliação parcial
    
    Reescrever os metodos 
        _amount_residual
        _get_lines 
        _compute_lines - usado para mostras pagamentos no formulario facturas   lin 144
            move_line_id_payment_get - da os id's das linhas de movimento relativas as contas dos parceiros - lin 397
        """
    _inherit = "account.invoice"
    
    '''
    def _amount_residual(self, cr, uid, ids, name, args, context=None):
        res = {}
        data_inv = self.browse(cr, uid, ids)
        for inv in data_inv:
            paid_amt = 0.0
            to_pay = inv.amount_total
            for lines in inv.move_lines:
                paid_amt = paid_amt - lines.credit + lines.debit
            res[inv.id] = to_pay - abs(paid_amt)
        return res  '''

    def _get_lines(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for id in ids:
            #move_lines = []
            ml = self.pool.get('account.move.line')
            for inv in self.read(cr, uid, ids, ['move_id']):
                if inv['move_id']:
                    move_lines = ml.search(cr, uid, [('move_id', '=', inv['move_id'][0])])
            
            if not move_lines:
                res[id] = []
                continue
            data_lines = self.pool.get('account.move.line').browse(cr,uid,move_lines)
            for line in data_lines:
                ids_line = []
                if line.reconcile_id:
                    ids_line = line.reconcile_id.line_id
                elif line.reconcile_partial_id:
                    ids_line = line.reconcile_partial_id.line_partial_ids
                l = map(lambda x: x.id, ids_line)
                res[id]=[x for x in l if x <> line.id]
        print '+++++++++++ sub classe  +++++++++++++\n'
        return res

    '''
    def move_line_id_payment_get(self, cr, uid, ids, *args):
        ml = self.pool.get('account.move.line')
        res = []
        for inv in self.read(cr, uid, ids, ['move_id','account_id']):
            if inv['move_id']:
                move_line_ids = ml.search(cr, uid, [('move_id', '=', inv['move_id'][0])])
                for line in ml.read(cr, uid, move_line_ids, ['account_id']):
                    if line['account_id']==inv['account_id']:
                        res.append(line['id'])
        return res'''
        
account_invoice()