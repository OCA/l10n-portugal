#! -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2008 Paulino . <paulino1@sapo.pt> All Rights Reserved.
#
##############################################################################


from mx import DateTime
import time
from osv import fields,osv
import pooler, wizard, tools
import pdb


class account_receipt(osv.osv):
    _name = "account.receipt"
    _description = "Invoice's receipts (wizard)"
    _columns = {
        'name': fields.char('Name', size=15, required=True),
        'partner_id': fields.many2one('res.partner', 'Partner', required=True),  # set null ???
        'address_id': fields.many2one('res.partner.address', 'Address', readonly=True, # required=True, 
                                states={'draft':[('readonly',False)]}),
        'date':  fields.date('Date', required=True),
        'value': fields.float('Valor', required=True, digits=(16, 3)),
        'lines': fields.one2many('account.receipt.line', 'receipt_id', 'Facturas'),
        'move_id': fields.many2one('account.move', 'Receipt Move', readonly=True), 
        'notes':   fields.text('Notes'),
        'state':   fields.selection([
                        ('draft', 'Draft'),
                        ('cancel','Cancelled'),
                        ('done','Done')], 'State', select=True)
    }
    _defaults = {
        'date':  lambda *a: DateTime.today().strftime('%Y-%m-%d'),
        'state': lambda *a: 'draft'
        }
    
account_receipt()


class account_receipt_line(osv.osv):
    _name = "account.receipt.line"
    _description = "Subscription document fields"
    _rec_name = 'field'
    _columns = {
        'receipt_id': fields.many2one('account.receipt', 'Receipt', required=True),
        'invoice_id': fields.many2one('account.invoice', 'Invoice', required=True), 
        'name':       fields.char('Name', size=15 ),
        'amount': fields.float('Amount', digits=(16,2)),
        #'paid_amount': fields.float('Paid Amount', digits=(16,2)),
    }
    _defaults = {}
    
account_receipt_line()



class wizard_receipt(osv.osv_memory):
    _name = "wizard.receipt"

    
    def _partner(self, cr, uid, context={}):
        partner_obj=self.pool.get('res.partner')
        ids=partner_obj.search(cr, uid, [])    # test line
        partners=partner_obj.browse(cr, uid, ids)
        return [(partner.id, partner.name) for partner in partners]


    def act_cancel(self, cr, uid, ids, context=None):
        return {'type':'ir.actions.act_window_close' }

    def act_destroy(self, *args):
        return {'type':'ir.actions.act_window_close' }

    def get_invoices(self, cr, uid, ids, context=None):   #get_invoices
        """Get the open invoices for actual partner to select wich ones to pay        """
        rec_id = ids[0]
        this = self.browse(cr, uid, rec_id)
        inv_obj = self.pool.get("account.invoice")
        print this.partner_id.id
        inv_ids = inv_obj.search(cr, uid, [ ('partner_id', '=', this.partner_id.id), 
                                        ('type', 'in',["out_invoice","out_refund"]),
                                        ('state', '=', 'open') ] )
        wiz_lines = self.pool.get('wizard.receipt.lines')
        vals = None
        # distribui o 'total a pagar' pelas facturas em aberto
        total = this.total
        for invoice in inv_obj.browse(cr, uid, inv_ids) :
            inv_pay = min( total, invoice.residual)
            vals = {  'rec' : rec_id,
                      'invoice_id': invoice.id,
                      'inv_move':   invoice.move_id.id,
                      'inv_date':   invoice.date_invoice,
                      'inv_number': invoice.number,
                      'due_date':   invoice.date_due,
                      'inv_total':  invoice.amount_total,
                      'inv_residual': invoice.residual,
                      'to_pay':       total > 0 and 1 or 0,
                      'paid_amount':  inv_pay,
                      }
            total -= inv_pay
            wiz_lines.create(cr, uid, vals,  context=context)
        if vals:
            return self.write(cr, uid, ids, {'state':'get'}, context=context)
        raise osv.except_osv(_('Warning'), _('Selected Partner has no open invoices!'))
        return


    def create_receipt(self, cr, uid, ids, context=None):
        "Create receipt, receipt lines, create account_move and reconcile this move with invoices in receipt lines"
        this = self.browse(cr, uid, ids[0] )

        rec_lines = []
        moves2reconcile = []                # ids of invoice's moves ids to reconcile
        total = 0
        for line in this.lines :
            # TODO: add account_move_line.id to receipt_line
            rec_lines.append((0,0, {'invoice_id': line.invoice_id, 'amount': line.paid_amount} ))
            total += line.paid_amount
            moves2reconcile.append( line.inv_move )             

        #stores move and move_line
        # TODO: add field to force period
        #        then if not period_id:  get o period by date
        #        period_ids= self.pool.get('account.period').search(cr,uid,[('date_start','<=',inv.date_invoice or time.strftime('%Y-%m-%d')),('date_stop','>=',inv.date_invoice or time.strftime('%Y-%m-%d'))])

        # get sequence number for receipt
        receipt_num = self.pool.get('ir.sequence').get_id(cr, uid, this.journal.invoice_sequence_id.id, context=context) or '/'
        partner_account_id = self.pool.get('res.partner').browse(cr, uid, this.partner_id.id).property_account_receivable.id
        
        move_lines = [(0,0, {   'date': this.rec_date, 
                                'name': receipt_num,
                                'partner_id': this.partner_id.id,
                                'account_id': this.journal.default_debit_account_id.id,
                                #'ref': receipt_num,
                                'debit': total,  
                                'credit': 0} ),
                      (0,0, { 'date': this.rec_date,
                              'name': receipt_num,
                              'partner_id': this.partner_id.id,
                              'account_id': partner_account_id,
                              #'ref': receipt_num,  
                              'credit':  total, 
                              'debit': 0} ) ]
        
        move = {'ref': receipt_num, 
                'line_id': move_lines, 
                #'period_id': 5,
                'journal_id': this.journal.id, 
                'date': this.rec_date, 
                'partner_id': this.partner_id.id}
        #print move
        move_obj = self.pool.get('account.move')
        move_id = move_obj.create(cr, uid, move)
        
        moves2reconcile.append(int(move_id))
        move_line_obj = self.pool.get('account.move.line')
        moveLines2reconcile = move_line_obj.search(cr, uid, [('account_id', '=', partner_account_id),
                                                             ('move_id', 'in', moves2reconcile ) ] )
        # TODO: get all related lines previously partial reconcileed
        # so they all become totally reconciled and invoice state can be set as done
        try :
            reconcile_id = move_line_obj.reconcile( cr, uid, moveLines2reconcile, type='receipt', context=context)
        except :
            partial_reconcile_id = move_line_obj.reconcile_partial( cr, uid, moveLines2reconcile, type='receipt', context=context)
        
        # save receipt
        receipt = { 'name': receipt_num, 
                    'partner_id': this.partner_id.id, 
                    'date': this.rec_date ,
                    'value':total, 
                    'lines':rec_lines, 
                    'move_id': move_id}
        receipt_id = self.pool.get('account.receipt').create(cr, uid, receipt)
        # TODO: print receipt automatically
        return self.write(cr, uid, ids, {'state':'done'}, context=context)

    _columns = {
        'partner_id': fields.many2one('res.partner', 'Partner', required=True),
        'note':      fields.text('Notes'),
        'rec_date':  fields.date('Date'),
        'total':     fields.integer('Total'),
        'journal':   fields.many2one('account.journal', 'Journal'),
        'lines':     fields.one2many('wizard.receipt.lines', 'rec', 'Lines'),
        'state':     fields.selection( ( ('choose','choose'),   ('get','get'), ('done', 'done')  ) ),
        }

    def _default_journal(self, cr, uid, ids, context={} ):
        try: return self.pool.get('account.journal').search(cr, uid, [('type', '=', 'cash'), ('active', '=', '1')])[0]
        except: return ''
        
    _defaults = {
        'state': lambda *a: 'choose',
        'rec_date': lambda *a : DateTime.today().strftime('%Y-%m-%d'),
        'journal': _default_journal
        }
wizard_receipt()



class wizard_receipt_lines(osv.osv_memory):
    _name = "wizard.receipt.lines"

    _columns = {
        'rec':       fields.many2one('wizard.receipt', 'Receipt'),
        'invoice_id': fields.integer('Invoice'),
        'inv_move': fields.integer('Move'),                    # move line to reconcile
        'inv_date': fields.date('Date'),
        'due_date': fields.date('Due date'),
        'inv_number': fields.char( 'Number', size=16),
        'inv_total': fields.float('Invoice amount',  digits=(16, 2)),
        'inv_residual': fields.float('Residual amount',  digits=(16, 2)),
        'to_pay':       fields.boolean('To Pay?'),
        'paid_amount':  fields.float('Amount to pay', digits=(16, 2)),
        }
    _defaults = { }

    def onchange_topay(self, cr, uid, ids, to_pay, residual):
        if to_pay:
            return {'value': {'paid_amount': residual}  , 
                    'readonly': {'paid_amount': "False"} 
                    }
        return {'value': {'paid_amount': 0.0} , 
                'readonly': {'paid_amount': "True"} 
                }
                
    def onchange_paid_amount(self, cr, uid, ids, amount, residual):
        if amount > residual:
            return {'value': {'paid_amount': residual,
                              'to_pay': True} }
        if amount <= 0 :
            return {'value': {'paid_amount': 0,
                              'to_pay': False} }
        return {'value': {'to_pay': True} }


wizard_receipt_lines()
