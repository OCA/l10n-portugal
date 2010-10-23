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
#import M2Crypto
import binascii

# Key file must be found in openerp/server/bin/keys
# One must create directory openerp/server/bin/keys and put a PEM private
# key there. To generate a private key execute:
#    openssl genrsa -out PrivateKey.pem 1024
# To generate the public one execute:
#    openssl rsa -in PrivateKey.pem -out PublicKey.pem -outform PEM -pubout
PRIV = RSA.load_key('keys/PrivateKey.txt')

def encrypt_data(InvoiceDate, SystemEntryDate, InvoiceNo, GrossTotal, LastHash):
    # generate concatenated string to encrypt
    message = '%s;%s;%s;%.2f;%s' % (InvoiceDate, SystemEntryDate, \
                                 InvoiceNo, GrossTotal, LastHash)
    p = getattr(RSA, 'pkcs1_padding')
    encrypted = PRIV.private_encrypt(message, p)
    print '[' + encrypted + ']'
    print '[' + binascii.b2a_base64(encrypted) + ']'
    return binascii.b2a_base64(encrypted)

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def write(self, cr, uid, ids, vals, context=None):
        print encrypt_data("2010-10-20", "2010-10-23", "2010/234", \
                        2345.6789, "QWERTYlast.hash.example")
        return super(account_invoice, self).write(cr, uid, ids, vals, context)
"""
    A questão que eu coloco é que temos de saber exactamente qual é a última
    factura confirmada. Pois temos de ir buscar o hash. Ora a factura id-1,
    pode estar apenas no estado draft, pro-forma ou ter sido apagada.
    Confio que o código actual que gera o número da factura, se encarregue de
    descobrir qual é, pois se testares verificas que mesmo que haja várias facturas
    pelo meio em draft ou pro-forma, ou até inexistente, pois podes apagar uma
    factura draft e esse id desaparece, ele vai buscar o número da última emitida.
    Talvez não esteja a ver bem como está a funcionar o openerp, mas ainda não
    vi ao certo como fazê-lo de forma simples, garantindo que estou de facto a
    utilizar o hash da última factura.
    Depois de perceber isto é claro que só se muda na confirmação.
    A ideia da lista de imutáveis é boa.
        Para prevenir eventuais alterações do wkf pelo aditor do cliente web, que invalidassem a assinatura:
         * define uma lista de campos imutaveis, após a factura estar confirmada - estados open, paid, ou cancel.
         * procura esses campos nas chaves do dict 'vals' e elimina-os se estiverem presentes
         * prossegue com a gravação de outras alterações
         * previne modificações do status, deposi de open so pode passar a paid ou cancel
            - deve permitir anulação do pagamento
"""
"""
        fixed = ['partner_id', 'type', 'internal_number', 'date_invoice', 'hash', 'hash_control', 'amount_antaxed', 'amount_tax', 'amount_total']
        for id in ids:
            record = self.read( cr, uid, [id], ['state'])[0]
            if record['state'] in ('open', 'paid', 'cancel'):
                for field in fixed:
                    if field in vals:
                        vals.pop(field)
        
        res = super(account_invoice, self).write(cr, uid, ids, vals, context=context)
        if 'state' in vals and vals['state'] == 'open':
            
            # todo: ler os campos que sao objecto da assinatura
            
            # todo: calcular a assinatura

            # todo: Gravar a assinatura na BD
            cr.execute("UPDATE account_invoice SET hash = " + signature
            + " WHERE id = " + str(id) )
        
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
"""
account_invoice()
