#! -*- encoding: utf-8 -*-
##############################################################################
#
#    Digital signature module for OpenERP, signs with an RSA private key the invoices
#    in complyance to the portuguese law - Decree nº 363/2010, of the 23rd June.
#    Copyright (C) 2010 Paulino Ascenção <paulino1@sapo.pt>
#
#    This file is a part of l10n_pt_digital_signature
#
#    l10n_pt_digital_sign is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    l10n_pt_digital_sign is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
##############################################################################

import os, datetime
from osv import osv, fields
from tools.translate import _

# indicar o caminho absoluto ou relativo a server/bin
priv_key = '/media/vista/OpenERP/6/addons_extra/l10n_pt_dig_sign/privatekey.pem'
hash_control = 1
passphrase='senhamaisdificil'

class account_invoice(osv.osv):
    _inherit = 'account.invoice'
        
    def get_hash(self, cr, uid, inv_id):
        """Gets the previous invoice of the same type and journal, and returns it's signature to be included in next invoice's string to sign
        """
        res = {}
        #invoice_obj=self.pool.get('account.invoice')
        invoice = self.browse(cr, uid, inv_id)
        cr.execute("SELECT hash FROM account_invoice inv \
                    WHERE internal_number = (\
                        SELECT MAX( internal_number) FROM account_invoice \
                        WHERE journal_id = " +str(invoice.journal_id.id)+" \
                            AND internal_number < '"+ invoice.internal_number +"'\
                            AND period_id in (SELECT id FROM account_period WHERE fiscalyear_id = "+str(invoice.period_id.fiscalyear_id.id)+") \
                            AND state in ('open', 'paid', 'cancel') )" )
        res = cr.fetchone()
        if res is None:
            return ''
        else :  
            return res[0]

    _defaults = {
        'hash_control': lambda *a: hash_control
        }
    
    def action_signature(self, cr, uid, ids, context=None):
        """Write hash and system_entry_date """
        # duvida: usar esta accao ou adicionar action_sign a incluir num workflow redesenhado, que substitua o original ????
        for invoice in self.browse(cr, uid, ids):
            # if invoice.state in ('open', 'paid', 'cancel') # not necessary, wkf determines properlly when this action is called
            # continues when it is not necessary to sign the invoices
            if (invoice.type in ('out_refund','out_invoice') and invoice.journal_id.self_billing) or (invoice.type in ('in_refund','in_invoice') and not invoice.journal_id.self_billing ) :
                continue
            inv_date = unicode(invoice.date_invoice)
            now = invoice.system_entry_date or datetime.datetime.now()
            invoiceNo = unicode(invoice.journal_id.saft_inv_type+' '+invoice.number)
            gross_total = self.grosstotal(cr, uid, invoice.id)
            prev_hash = self.get_hash(cr, uid, invoice.id)
            message = inv_date+';'+str(now)[:19].replace(' ','T')+';'+invoiceNo+';'+gross_total+';'+prev_hash
            print message
            signature = os.popen('echo -n "'+message+'" | openssl dgst -sha1 -sign '+priv_key+' -passin pass:'+passphrase+' | openssl enc -base64 -A', "r").read()
            #signature = os.popen('echo -n "'+message+'" | openssl dgst -sha1 -sign '+priv_key2+' | openssl enc -base64 -A', "r").read()
            cr.execute("UPDATE account_invoice SET hash = '%s' WHERE id = %d" %(signature, invoice.id) )
            if not invoice.system_entry_date:
                cr.execute("UPDATE account_invoice SET system_entry_date = '%s' WHERE id = %d" %(now, invoice.id) )
        return True

#    def action_cancel(self, cr, uid, ids, *args):
#        invoices = self.read(cr, uid, ids, ['move_id'])
#        for i in invoices:
#            if i['move_id']:
#                #todo: apenas facturas assinadas não podem ser anuladas - criterios acima
#                raise osv.except_osv(_('Error !'), _('You cannot cancel confirmed Invoices!'))
#                return False                        
#        self.write(cr, uid, ids, {'state':'cancel', 'move_id':False})
#        self._log_event(cr, uid, ids, -1.0, 'Cancel Invoice')
#        return True


account_invoice()
