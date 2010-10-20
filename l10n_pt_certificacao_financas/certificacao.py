# -*- encoding: utf-8 -*-
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
from osv import osv
from M2Crypto import RSA

import binascii

RSA = RSA.load_key("keys/PrivateKey.pem")

def m2c_sign(InvoiceDate, SystemEntryDate, InvoiceNo, GrossTotal, LastHash):
    # generate concatenated string to encrypt
    message = '%s;%s;%s;%.2f;%s' % (InvoiceDate, SystemEntryDate, \
                                 InvoiceNo, GrossTotal, LastHash)
    encrypted = RSA.private_encrypt(message, RSA.pkcs1_padding)
    return binascii.b2a_base64(encrypted)

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def write(self, cr, uid, ids, vals, context=None):
        # TODO: This is not correct!
        #  Because there is a possibility to create for example the invoice 10
        #  but invoice 9 be in state PRO-FORMA with no hash and no relevance
        #  for tax purposes.
        #  It must get the last created and confirmed invoice from database.
        #  It must be in code where Invoice Number is created, not here.
        #  Must also check if hash was generated to prevent any future change.
        return super(account_invoice, self).write(cr, uid, ids, vals, context)
    
        hashes = self.read(cr, uid, ids, ['hash'])
        for nohash in hashes:
            if nohash['hash'] == '':
                if 'state' in vals and vals['state'] == 'open':
                    # Get tax related fields to be encrypted
                    invoices = self.read(cr, uid, ids, \
                                         ['date_invoice','system_write_date', \
                                          'number', 'amount_total'])
                    for invoice in invoices:
                        if invoice['id'] == 1:
                            # If this is the first invoice means that there is
                            # no last_invoice_hash, so hash must be empty
                            last_hash = ''
                        else:
                            last_invoice = self.read(cr, uid, \
                                                     [invoice['id'] - 1], \
                                                     ['hash'])
                            last_hash = last_invoice[0]['hash']
                        # todo: calcular a assinatura
                        hash = m2c_sign(invoice['date_invoice'], \
                                        invoice['system_write_date'], \
                                        invoice['number'], \
                                        invoice['amount_total'], \
                                        last_hash)
                        # todo: Gravar a assinatura na BD
                        self.write(cr, uid, [invoice['id']], {'hash': hash})
                        return super(account_invoice, self).write(cr, uid, \
                                     ids, vals, context)
            else:
                # already has hash don't change anything for now
                # in future limit changes to fields with no tax relation
                return
account_invoice()
