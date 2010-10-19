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

import M2Crypto.RSA
import binascii

RSA = M2Crypto.RSA.load_pub_key("keys/PrivateKey.pem")

def m2c_encrypt(InvoiceDate, SystemEntryDate, InvoiceNo, GrossTotal, LastHash=""):
    # generate concatenated string to encrypt
    text = InvoiceDate + ";" + SystemEntryDate + ";" + InvoiceNo + ";" + \
           GrossTotal + ";" + LastHash
    hash = RSA.public_encrypt(text, M2Crypto.RSA.pkcs1_padding)
    print "Invoice Hash: [" + text + "][" + binascii.b2a_base64(hash) + "]"
    return binascii.b2a_base64(hash)

# This function is used just for testing purposes
# should be removed later
def m2c_decrypt(hash):
    encrypted = binascii.a2b_base64(hash)
    priv_key = M2Crypto.RSA.load_key("keys/PrivateKey.pem")
    decrypted = priv_key.private_decrypt(encrypted, M2Crypto.RSA.pkcs1_padding)
    return decrypted

class invoice_certified_l10n_pt(osv.osv):
    _name = "account.invoice" account.
    _inherit = "account.invoice"
    
    def write(self, cr, uid, ids, vals, context=None):
        #check if this is only called once!! on invoice confirmation!
        if 'state' in vals and vals['state'] == 'open':
            # todo: ler os campos que sao objecto da assinatura
            reads = self.read(cr, uid, ids, \
                              ['id', 'date_invoice','write_date', \
                               'number', 'amount_total'])
            if reads.id == 1:
                # If this is the first invoice there is no last invoice hash
                last_hash = ""
            else:
                last_invoice_id = reads.id - 1
                last_invoice = self.search(cr, uid, [('id', [last_invoice_id])])
                last_hash = last_invoice.hash
            # todo: calcular a assinatura
            hash = m2c_encrypt(reads.date_invoice, reads.write_date, \
                               reads.number, reads.amount_total, \
                               last_hash)
            # todo: Gravar a assinatura na BD
            self.write(cr, uid, [reads.id], {'hash': hash})
        return super(invoice_certified_l10n_pt, self).write(cr, uid, ids, \
                                                            vals, context)
invoice_certified_l10n_pt()
