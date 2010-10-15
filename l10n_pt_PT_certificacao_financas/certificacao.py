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

##############################################################################
#
# 08/10/2010 - Links úteis por Carlos Almeida,
#
# No seguinte site são explicados alguns dos problemas que irão surgir, se se
# utilizar o OpenSSl da forma que é sugerida:
#  * http://www.cryptosys.net/pki/portugal_DGCI_billing_software.html
# Existe um exemplo em Java:
#  * http://code.google.com/p/javacertpt/
#
##############################################################################
#
# 07/10/2010 - Explicação geral feita por Paulino,
#
# Portaria 363/2010 e especificação técnica disponíveis em:
#  * http://info.portaldasfinancas.gov.pt/pt/apoio_contribuinte/CertificacaoSoftware.htm
# A certificação depende do saft - para ser certificado um programa de
# facturação tem de ser capaz de emitir o saft. O saft é obrigatório, já a
# certificação não é necessária em qualquer dos seguintes casos:
#  * Software produzido internamente, do qual a entidade seja dona dos direitos
#    de autor;
#  * Os clientes não sejam consumidores finais - nenhum;
#  * Vendas inferiores a € 150.000;
#  * Número de facturas emitidas menor que 1.000 / ano.
# Nas especificações técnicas, disponíveis na ligação acima, são apresentados
# exemplos de como gerar as chaves publica e privada, como assinar cada factura
# emitida com recurso ao OpenSSL.
# Há uma módulo RSA em python para assinaturas e encriptação - http://stuvel.eu/rsa.
# Há uma incongruência: O saft requer dois valores Hash e HashControl ambos com 40
# caracteres. Nos exemplos dados nas especificações técnicas, o cumprimento da
# assinatura é 172 caracteres...
# Segundo esclarecimento que obtive será publicada uma actualização ao saft, para
# alargar o campo Hash para 200 caracteres
# A chave privada, necessária para assinar as facturas, é do conhecimento
# exclusivo do produtor do software! O ficheiro que contém a chave privada,
# deve ser convertido em binário ou encriptado (?)
#
##############################################################################

from osv import fields
from osv import osv


class account_invoice(osv.osv):
    _inherit = "account.invoice"
    
    """ 
    A assinatura não acontece no estado 'draft', mas sim quando a factura é confirmada e é atribuido o numero.
    Personaliza o metodo write, quando ou apos mudar o estado para 'open'
    A data relevante para o saft   é o 'write_date', porque a factura é criada sempre no estado 'draft' 
    e só é verdadeiramente uma factura, quando é confirmada
    """

    def write(self, cr, uid, ids, vals, context=None):
        
        res = super(account_invoice, self).write(cr, uid, ids, vals, context=context)
        if 'state' in vals and vals['state'] == 'open':
            # todo: ler os campos que sao objecto da assinatura
            
            # todo: calcular a assinatura

            # todo: Gravar a assinatura na BD
            cr.execute("UPDATE account_invoice SET hash = " + signature
            + " WHERE id = " + str(id) )
        



#class invoice_l10n_pt_PT_certified(osv.osv):
#    _name = "account.invoice"
#    _inherit = "account.invoice"
#    _columns = {
#        'system_entry_date': fields.datetime('System Entry Date', states={'open':[('readonly',True)],'close':[('readonly',True)]}),
#        'hash'
#    }
#invoice_l10n_pt_PT_certified

print "\n=====RSA 368 Demo====="
#use 1 RSA key to encrypt the AES key
#use another RSA key to sign AES key
from Crypto.PublicKey import RSA
from Crypto import Random

#start the random generator
rpool = Random.new()
Random.atfork()

# generate both RSA keys,
privatekeyCMS = RSA.generate(1024, rpool.read)
Random.atfork()
privatekeyClient = RSA.generate(1024, rpool.read)
publickeyCMS = privatekeyCMS.publickey()
publickeyClient = privatekeyClient.publickey()

#sign the AES PWD with server private key
signed_PWD = privatekeyCMS.sign(PWD,"")
#encrypt AES PWD with client public key
enc_PWD = publickeyClient.encrypt(PWD, "")
print "with publickeyClient encrypted AES-PWD:"
print enc_PWD[0].encode("hex"),"\n"
print "with privatekeyCMS signed AES-PWD:"
print signed_PWD[0],"\n"

#decryption
dec_PWD= privatekeyClient.decrypt(enc_PWD[0])
#verify identity of the
print "key verify:\n",publickeyCMS.verify(dec_PWD,signed_PWD)
print "decrypted PWD:\n",dec_PWD
