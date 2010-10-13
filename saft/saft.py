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

import datetime
import tools
import base64
import cStringIO
import csv
import pooler
from osv import fields,osv
from xml.etree import ElementTree as et
#from xml.dom.minidom import parseString
import copy
import netsvc
logger = netsvc.Logger()

from invoice import SoftCertNr
##VALORES FIXO do cabecalho relativos ao OpenERP
_ProductCompanyTaxID = '508115809'  
_ProductId =        'OpenERP/Observideia'
_ProductVersion =   '5'
_HeaderComment =    u'Software criado por Tiny sprl<www.tiny.be> a adaptado por Observideia Lda<observideia@sapo.pt>'


class res_partner(osv.osv):
    """Adiciona os campos requeridos pelo SAFT relativos a clientes e fornecedores
    conservatória e numero do registo comercial"""
    _inherit = 'res.partner'
    _columns = {
        #'ref': fields.char('Code', size=64, required=True),
        'reg_com' : fields.char('N.Registo', 32, help="Número do registo comercial"),
        'conservatoria' : fields.char('Conservatoria', 64, help="Conservatória do registo comercial"),
        }
res_partner()


class res_company(osv.osv):
    _inherit = 'res.company'
    _columns = {
        'open_journal' : fields.many2one('account.journal', 'Diário de Abertura')
    }
res_company()


class account_tax(osv.osv):
    _inherit = 'account.tax'
    _columns = {
        'area_fiscal' : fields.selection([('CON', 'Continente'), ('RAA', 'Açores'), ('RAM', 'Madeira')], 'Espaço Fiscal'),
        'nivel_taxa'  : fields.selection([('Isenta', 'Isenta'), ('Reduzida', 'Reduzida'), ('Normal', 'Normal'),
                     ('Intermedia', 'Intermédia'), ('Outra', 'Outra')],'Nível de Taxa'),
                }
account_tax()


## TODO em vez de 1 grande elemento mantido na memoria, criar uma stream e gerar o texto com subelementos aos poucos


def AddressStructure(parent_tag, address, city, pcode, country, region=None):
    """Funcao para gerar campo Address 
    Elementos e ordem: 
        BuildingNumber  
        StreetName
      * AddressDetail
      * City
      * PostalCode
        Region
      * Country    """
    parent = et.Element( parent_tag )
    for el, txt in zip((  'AddressDetail', 'City', 'PostalCode', 'Region', 'Country'), 
                         ( address, city, pcode, region,  country)):
        if txt is None :
            if el == 'Country' : txt = 'PT'
            elif el == 'Region': continue
            else : txt = 'Desconhecido'
        i=et.SubElement(parent, el)
        i.text=txt
        i.tail = '\n'
    return  parent 


def date_format(data, tipo='DateType'):
    d = datetime.datetime.strptime(data[:19], '%Y-%m-%d %H:%M:%S')
    if tipo == 'DateType':
        return d.strftime('%Y-%m-%d')
    else :
        return d.strftime('%Y-%m-%dT%H:%M:%S')
    
    
tipos_saft = [  ('C', 'Contabilidade'),                         # ctb na v.1
                ('F', u'Facturação'),                           # fact na v.1
                ('I', u'Integrado - Contabilidade e Facturação'), # int
                ('S', u'Autofacturação'),                         # novo v.2
                ('P', u'Dados parciais de facturação')    ]        # novo v.2


class wizard_saft(osv.osv_memory):

#    def _get_year(self, cr, uid, context):
#        """Obtem o exercicio fiscal para o qual gerar o saft-pt 
#        Mostrar uma lista para seleccao com os exercicios existentes para a companhia actual"""
#        
#        year_obj=self.pool.get('account.fiscalyear')
#        ids=year_obj.search(cr, uid, [])    # testar esta linha
#        # talvez basta usar o browse, porque nao preciso de filtrar por ids - todos os anos sao validos (excepto os nao começados...)
#        years=year_obj.browse(cr, uid, ids)
#        return [(year.id, year.name) for year in years]
    
    _name = "wizard.l10n_pt.saft"
    _columns = {
            'name': fields.char('Filename', 16, readonly=True),
            'year': fields.many2one('account.fiscalyear', 'Exercício', required=True),
            'comp': fields.many2one('res.company', 'Companhia', required=True), 
            'tipo': fields.selection(tipos_saft,'Tipo ficheiro'),
            'data': fields.binary('File', readonly=True),
            'state': fields.selection( ( ('choose','choose'),   # choose fiscal year
                                         ('get','get'),         # get the file
                                       ) ),
           # TODO - adicionar campo para tipo do saft
            }
    _defaults = { 'state': lambda *a: 'choose', }

    def act_cancel(self, cr, uid, ids, context=None):
        #self.unlink(cr, uid, ids, context)
        return {'type':'ir.actions.act_window_close' }

    def act_destroy(self, *args):
        return {'type':'ir.actions.act_window_close' }

    def getAddress(self, cr, uid, partner_id, tipo='default'):
        cr.execute("SELECT id  FROM res_partner_address WHERE id = COALESCE( \
                 (SELECT MIN(id) FROM res_partner_address WHERE  partner_id=%d AND type = '%s') , \
                 (SELECT MIN(id) FROM res_partner_address WHERE  partner_id=%d ))" %(partner_id, tipo, partner_id))
        address_id = cr.fetchone()[0]
        
        cr.execute("SELECT ad.street||COALESCE(' '||ad.street2, ''), ad.city, ad.zip, c.code, r.name, \
                            COALESCE(ad.phone, ad.mobile), ad.fax, ad.email \
                    FROM res_partner_address ad \
                        LEFT JOIN res_country c ON c.id = ad.country_id \
                        LEFT JOIN res_country_state r ON r.id  = ad.state_id \
                    WHERE ad.id ="+ str(address_id) ) 
        address = cr.fetchone()
        #print address
        return address
    
    def act_getfile(self, cr, uid, ids, context=None):
        """Gera o conteudo do ficheiro xml 
        """
        
        self.this = self.browse(cr, uid, ids[0])
        #Namespaces declaration
        self.xmlns = "urn:OECD:StandardAuditFile-Tax:PT_1.00_01"
        attrib={'xmlns': self.xmlns, 'xmlns:xsi':"http://www.w3.org/2001/XMLSchema-instance",
                'xsi:noNamespaceSchemaLocation' : "saft-pt.xsd"}

        root = et.Element("AuditFile", attrib = attrib )
        header = et.SubElement(root, 'Header', xmlns=self.xmlns)
        header.tail = '\n'
        #master 
        root.append( self._get_masters(cr, uid) )
    
        #entries : exclui na facturação
        if self.this.tipo != 'fact':
            root.append( self._get_entries(cr, uid) )
        #for el in (header, master, entries) : 
        #    el.tail = '\n'
        
        et.SubElement(header, 'AuditFileVersion').text='1.00_01'
         
        cr.execute("""
            SELECT p.id, p.vat, p.name, p.reg_com, p.conservatoria, p.website
            FROM res_partner p
            WHERE p.id = (SELECT partner_id FROM res_company) """  )
        
        p_id, vat, name, registo, conserv, web = cr.fetchone()
        street, city, zipc, country, state, phone, fax, mail = self.getAddress(cr, uid, p_id)
        
        for el, txt in zip(('CompanyID', 'TaxRegistrationNumber', 'TaxAccountingBasis',  'CompanyName'),
                           (str(conserv)+'/'+str(registo), vat, self.this.tipo, name )):
            et.SubElement(header, el).text=txt
        
        compAddress = AddressStructure( 'CompanyAddress', street, city, zipc, country, state)
        header.append( compAddress )
        
        # le o ano fiscal na base de dados
        fy_obj = self.pool.get('account.fiscalyear')
        fy = fy_obj.browse(cr, uid, self.this.year.id)
        #### gera o header propriamente
        tags = (    ('FiscalYear',      fy.code,),
                    ('StartDate',       fy.date_start),
                    ('EndDate',         fy.date_stop),
                    ('CurrencyCode',    'EUR'),
                    ('DateCreated',     '%s' %str(datetime.date.today()) ),
                    ('TaxEntity',       'Sede'),
                    ('ProductCompanyTaxId', _ProductCompanyTaxId),
                    ('SoftwareCertificateNumber', SoftCertNr)
                    ('ProductID',       _ProductID),
                    ('ProductVersion',  _ProductVersion),
                    ('HeaderComment',   _HeaderComment),
                    ('Telephone',       phone),
                    ('Fax',             fax),
                    ('Email',           mail),
                    ('Website',         web)
                    )
        for tag, valor in tags:
            if valor is None : 
                continue
            et.SubElement(header, tag).text=valor
        for element in header.getchildren() :
            element.tail = '\n'
        
        #SourceDocumentos se tipo não é 'ctb'
        if self.this.tipo != 'ctb' :
            root.append( self._write_source_documents( cr, uid, fy.date_start, fy.date_stop) )
        
        xml_txt = et.tostring(root, encoding="utf-8")
        #pretty = parseString(xml_txt).toprettyxml()
        out=base64.encodestring( xml_txt )   #buf.getvalue())
        #return self.write(cr, uid, ids, {'state':'get', 'data':out, 'advice':this.advice, 'name':this.name}, context=context)
        return self.write(cr, uid, ids, {'state':'get', 'data':out, 'name':"saftpt.xml"}, context=context)
    
        
    def _get_masters(self, cr, uid, context={}):
        logger.notifyChannel("saft :", netsvc.LOG_INFO, 'A exportar MasterFiles')
        master = et.Element('MasterFiles', xmlns=self.xmlns)
        master.tail='\n'
        # 2.1 GeneralLedger
        # obtem lista de contas com movimentos, com saldos de abertura
        # precisa obter contas-mãe para cada cta de movimento
        if self.this.tipo != 'fact' :
            cr.execute("SELECT DISTINCT ac.id, ac.code, ac.name, ac.parent_id, COALESCE(debito, 0.0), COALESCE(credito, 0) \
                FROM account_move_line ml \
                	INNER JOIN account_account  ac  ON  ac.id = ml.account_id\
                	LEFT JOIN (SELECT account_id, SUM( debit) AS debito, SUM( credit ) AS credito\
                    		   FROM account_move_line WHERE journal_id = \
                    		   (SELECT open_journal FROM res_company WHERE id = "+str(self.this.comp.id)+") \
                    		   GROUP BY account_id)  abertura  ON  ml.account_id = abertura.account_id")
            acc_dict = {}
            acc_obj = self.pool.get('account.account')
            for ac_id, code, name, parent, debit, credit in cr.fetchall():
                #print code, name, parent, debit, credit
                acc_dict[ code ] = {'name':name, 'debit':debit, 'credit':credit}
                account = acc_obj.browse(cr, uid, parent )
                while account :
                    if len(account.code) < 2 :
                        break
                    try :
                        acc_dict[account.code]['debit']  += debit
                        acc_dict[account.code]['credit'] += credit
                    except KeyError :
                        acc_dict[account.code] = {'name':account.name, 'debit':debit, 'credit':credit}
                    account = account.parent_id
            
            logger.notifyChannel("saft :", netsvc.LOG_INFO, 'A exportar tabela de contas (GeneralLedger)')
            for code in sorted( acc_dict ):
                gl = et.SubElement(master, 'GeneralLedger')
                gl.tail='\n'
                et.SubElement(gl, 'AccountID').text=code
                et.SubElement(gl, 'AccountDescription').text = acc_dict[code]['name']#.decode('utf8')
                et.SubElement(gl, 'OpeningDebitBalance').text= str( acc_dict[code]['debit'] )
                et.SubElement(gl, 'OpeningCreditBalance').text= str( acc_dict[code]['credit'] )
                for element in gl.getchildren():
                    element.tail='\n'
                
        ####   2.2 Customer;    2.3 Supplier  =========================================
        #CustomerID	(Supplier)      * partner.id | partner.ref
        #CustomerTaxID (Supplier)   * partner.vat
        #CompanyName                * partner.name
        #Contact	                  [address.name (default)]
        #BillingAddress	            * address[invoice|default]
        #ShipToAddress	              address[delivery]
        #Telephone	                  address[default].phone | mobile
        #Fax	                      address[default].fax
        #Email	                      address[default].email
        #Website	                  partner.website
        cr.execute("SELECT p.id, p.name, p.vat, p.website \
                    FROM res_partner  p \
                    WHERE id NOT IN (SELECT partner_id FROM res_company) \
                    ORDER BY id")   
        supp_el = et.Element('Suppliers')
        logger.notifyChannel("saft :", netsvc.LOG_INFO, 'A exportar Clientes')
        for p_id, name, vat, web in cr.fetchall() :
            c = et.SubElement(master, 'Customer')
            c.tail='\n'
            et.SubElement(c, 'CustomerID').text = str(p_id)
            et.SubElement(c, 'CustomerTaxID').text = vat
            et.SubElement(c, 'CompanyName').text = name
            # get addres    Verifica se ha endereço. 
            # TODO : este controlo deveria estar dentro da funcção getAddress
            try :
                street, city, zipc, pais, regiao, phone, fax, mail = self.getAddress(cr, uid, p_id)
            except TypeError: 
                street = city = zipc = 'Desconhecido'
                pais = 'PT'
                regiao = phone = fax = mail = None
                
            c.append( AddressStructure('BillingAddress', street, city, zipc, pais, region=regiao) )
            # elementos facultativos
            for tag, text in zip( ('Telephone', 'Fax', 'Email', 'Website'), (phone, fax, mail, web)):
                if text is None :
                    et.SubElement(c, tag)
                et.SubElement(c, tag).text = text

            # Supplier nos tipos ctb e int
            if self.this.tipo != 'fact' :
                s = et.SubElement(supp_el, 'Supplier')
                for element in c.getchildren():
                    c.tail='\n'
                    if element.tag == 'CustomerID' : 
                        s_id = copy.copy( element) 
                        s_id.tag = 'SupplierID'
                        s.append(s_id)
                    elif element.tag == 'CustomerTaxID' : 
                        sTax=copy.copy( element)
                        sTax.tag = 'SupplierTaxID'
                        s.append(sTax)
                    else :
                        s.append(element)
        if self.this.tipo != 'fact' :
            logger.notifyChannel("saft :", netsvc.LOG_INFO, 'A exportar Fornecedores')
            for supplier in supp_el.getchildren():
                master.append( supplier )
            del supp_el
            
        # Product no tipo fact e int
        if self.this.tipo != 'ctb' :
            self._write_products(cr, uid, master)
            
        # 2.5 TaxTable
        master.append( self._get_taxes(cr, uid) )
        return master
        
    def _write_products(self, cr, uid, master):
        logger.notifyChannel("saft :", netsvc.LOG_INFO, 'A exportar tabela de produtos')
        ids = self.pool.get('product.product').search(cr, uid, [])
        products = self.pool.get('product.product').browse(cr, uid, ids)

        for product in products:
            eproduct = et.SubElement(master, "Product")
            eproduct_type = et.SubElement(eproduct, "ProductType")
            if product.type == 'product':
                eproduct_type.text = 'P'
            elif product.type == 'service':
                eproduct_type.text = 'S'
            else:
                eproduct_type.text = 'O'
            eproduct_code = et.SubElement(eproduct, "ProductCode")
            eproduct_code.text = unicode(product.default_code)
            eproduct_group = et.SubElement(eproduct, "ProductGroup")
            eproduct_group.text = product.categ_id.name
            
            eproduct_description = et.SubElement(eproduct, "ProductDescription")
            eproduct_description.text = product.name

            eproduct_number_code = et.SubElement(eproduct, "ProductNumberCode")
            if product.ean13:
                eproduct_number_code.text = product.ean13
            else:
                eproduct_number_code.text = product.default_code
        
    def _get_taxes(self, cr, uid, context={}):
        logger.notifyChannel("saft :", netsvc.LOG_INFO, 'A exportar TaxTable')
        taxTable = et.Element('TaxTable')
        cr.execute("SELECT DISTINCT area_fiscal, nivel_taxa, amount \
                    FROM account_tax WHERE parent_id is NULL \
                    ORDER BY area_fiscal, amount")
        for area, nivel, taxa in cr.fetchall():
            taxType = et.SubElement(taxTable, 'TaxType')
            et.SubElement(taxType, 'Description').text = 'IVA'+area
            details = et.SubElement(taxType, 'TaxCodeDetails')
            
            et.SubElement(details, 'TaxCode').text = nivel[:3]
            et.SubElement(details, 'Description').text = nivel
            et.SubElement(details, 'TaxPercentage').text = str(taxa*100)
        return taxTable
        
        
    def _get_entries(self, cr, uid, context={}):
        logger.notifyChannel("saft", netsvc.LOG_INFO, '... a exportar movimentos da contabilidade')
        entries = et.Element('GeneralLedgerEntries', xmlns=self.xmlns)
        entries.tail='\n'
        numberOfEntries = et.SubElement(entries, 'NumberOfEntries')
        num_entries = 0
        totalDebit = et.SubElement(entries, 'TotalDebit')
        total_debit = 0
        totalCredit = et.SubElement(entries, 'TotalCredit')
        total_credit = 0
        # dict para reunir id das contas com movimentos
        #self.acc_ids={}
        
        # obtem diarios excepto diario de abertura
        if not self.this.comp.open_journal :
            logger.notifyChannel("saft", netsvc.LOG_INFO, u'Falta definir o diário de abertura da companhia')
            raise osv.except_osv(_('Error !'), _('Diario Abertura'))
        cr.execute( " SELECT id, code, name, type FROM account_journal\
                      WHERE id <>" + str(self.this.comp.open_journal.id) )
        for j_id, j_code, j_name, j_type in cr.fetchall() :
            journal = et.SubElement(entries, 'Journal')
            et.SubElement(journal, 'JournalID').text = j_code
            et.SubElement(journal, 'Description').text = j_name
            
            # transaccoes do diario e exercicio
            cr.execute("\
                SELECT m.id, m.name, p.code, m.date, COALESCE( uc.login, uw.login), m.ref,\
                    COALESCE(m.write_date, m.create_date, m.date)\
                FROM account_move m\
                    INNER JOIN account_period p ON m.period_id = p.id\
                    INNER JOIN res_users uc ON uc.id = m.create_uid\
                    INNER JOIN res_users uw ON uw.id = m.write_uid\
                WHERE m.period_id IN (SELECT id FROM account_period \
                                      WHERE fiscalyear_id = "+str(self.this.year.id) +")\
                      AND m.journal_id = "+str(j_id)+" AND m.state = 'posted' \
                ORDER BY m.name")
           
            for move_id, trans_id, period, date, user, desc, post_date in cr.fetchall():
                num_entries += 1
                trans_el = et.SubElement(journal, 'Transaction')
                et.SubElement(trans_el, 'TransactionID').text = str(trans_id)
                et.SubElement(trans_el, 'Period').text = period
                et.SubElement(trans_el, 'TransactionDate').text = date
                et.SubElement(trans_el, 'SourceID').text = user
                trans_desc = et.SubElement(trans_el, 'Description')
                trans_desc.text = desc
                # data no formata AAAA-MM-DD cfr schema DateType e cfr FAQ 40, ao contrario do esquema de dados 
                #if isinstance(post_date, str) : print move_id, post_date
                et.SubElement(trans_el, 'GLPostingDate').text = date_format(post_date, 'DateType')
                # se diario é de vendas  - clientes ; se compras : fornecedores
                if j_type == 'sale':
                    partner_el = et.SubElement(trans_el, 'CustomerID')
                elif j_type == 'purchase':
                    partner_el = et.SubElement(trans_el, 'SupplierID')
                # Adiciona linhas dos movimentos
                # usar id interno para referenciar parceiros
                cr.execute("SELECT l.id, a.id, a.code, l.ref, COALESCE(l.write_date, l.create_date), \
                                    l.name, l.debit, l.credit, l.partner_id \
                        FROM account_move_line l\
                            INNER JOIN account_account a ON l.account_id = a.id\
                        WHERE l.move_id = "+str(move_id) + 
                        " ORDER BY l.id")
                
                # Assumir que em documentos de venda e de compra o parceiro é o mesmo em todas as linhas
                for line, acc_id, acc_code, source, date, ldesc, debit, credit, partner in cr.fetchall():
                    line_el = et.SubElement(trans_el, 'Line')
                    et.SubElement(line_el, 'RecordID').text=str(line)
                    et.SubElement(line_el, 'AccountID').text=acc_code
                    et.SubElement(line_el, 'SystemEntryDate').text= date_format( date, 'DateTimeType')
                    et.SubElement(line_el, 'Description').text=ldesc
                    if debit :
                        et.SubElement(line_el, 'DebitAmount').text=str(debit)
                        total_debit += debit
                    elif credit :
                        et.SubElement(line_el, 'CreditAmount').text=str(credit)
                        total_credit += credit
                    #self.acc_ids[acc_id] = 0
                    for element in line_el.getchildren():
                        element.tail='\n'            
                if j_type in ('sale', 'purchase'):
                    partner_el.text = str(partner)
                for element in trans_el.getchildren():
                    element.tail='\n'            
            for element in journal.getchildren():
                element.tail='\n'            
        numberOfEntries.text = str(num_entries)
        totalDebit.text = str(total_debit)
        totalCredit.text = str(total_credit)
        for element in entries.getchildren():
            element.tail = '\n'
        return entries

    def _write_invoice(self, cr, uid, invoice, eparent):
        # sub-elements
        einvoice_no = et.SubElement(eparent, u"InvoiceNo")
        eperiod = et.SubElement(eparent, u"Period")
        einvoice_date = et.SubElement(eparent, u"InvoiceDate")
        einvoice_type = et.SubElement(eparent, u"InvoiceType")
        esystem_entry_date = et.SubElement(eparent, u"SystemEntryDate")
        etransaction_id = et.SubElement(eparent, u"TransactionID")
        ecustomer_id = et.SubElement(eparent, u"CustomerID")

        if invoice.number:
            einvoice_no.text = unicode(invoice.number)
        # TODO: period name
        if invoice.period_id:
            eperiod.text = invoice.period_id.name
        if invoice.date_invoice:
            einvoice_date.text = unicode(invoice.date_invoice)
        #TODO: type can be "Factura", "Nota de Debito" "Nota de Credito" e "Venda a Dinheiro"
        if invoice.type:
            einvoice_type.text = unicode(invoice.type)
        # TODO system entry date ao segundo             date_format(data, tipo='DateType')
        cr.execute("SELECT COALESCE(write_date, create_date) FROM account_invoice WHERE id = %d" %invoice.id)
        esystem_entry_date.text = date_format(cr.fetchone()[0], tipo='DateTimeType')
        #etransaction_id.text = 'opcional'
        if invoice.partner_id:
            ecustomer_id.text = unicode(invoice.partner_id.id)

    def _write_source_documents(self, cr, uid, start_date, final_date):
        esource_documents = et.Element('SourceDocuments')
        logger.notifyChannel("saft", netsvc.LOG_INFO, 'A exportar facturas de vendas')
        # get invoices
        # TODO verificar facturas no estado 'cancel' que nao passaram pelo estado 'open'. devem se excluidas
        ids = self.pool.get('account.invoice').search(cr, uid, [('date_invoice', '>=', start_date), 
                ('date_invoice', '<=', final_date), ('state', 'in', ['open', 'paid','cancel']),
                ('type', 'in',["out_invoice","out_refund"]),])
        invoices = self.pool.get('account.invoice').browse(cr, uid, ids)

        esales_invoices = et.SubElement(esource_documents, "SalesInvoices")

        # totals
        enumber_of_entries = et.SubElement(esales_invoices, u"NumberOfEntries")
        etotal_debit = et.SubElement(esales_invoices, u"TotalDebit")
        etotal_credit = et.SubElement(esales_invoices, u"TotalCredit")
        enumber_of_entries.text = str(len(ids))
        total_debit = 0
        total_credit = 0

        # Invoice
        for invoice in invoices:
            einvoice = et.SubElement(esales_invoices, u"Invoice")
            self._write_invoice(cr, uid, invoice, einvoice)

            # ship to: client address
            eship_to = et.SubElement(einvoice, u"ShipTo")
            # TODO: deliveryID and date
            edelivery_id = et.SubElement(eship_to, u"DeliveryID")
            edelivery_date = et.SubElement(eship_to, u"DeliveryDate")
            #edelivery_id.text = ''
            # data da factura usada como data da entrega
            edelivery_date.text = invoice.date_invoice
            
            # Delivery address
            street, city, zipc, country, state, phone, fax, mail = self.getAddress( cr, uid, invoice.partner_id.id, tipo='delivery')
            ship_address = AddressStructure('Address', street, city, zipc, country, region=state)
            eship_to.append( ship_address)

            # ship from: company address
            eship_from = et.SubElement(einvoice, u"ShipFrom")
            # TODO: deliveryID and date
            edelivery_id = et.SubElement(eship_from, u"DeliveryID")
            edelivery_date = et.SubElement(eship_from, u"DeliveryDate")
            #edelivery_id.text = ''
            # Data da entrega igual à da factura
            edelivery_date.text =  invoice.date_invoice
            
            # address
            street, city, zipc, country, state, phone, fax, mail = self.getAddress( cr, uid, self.this.comp.partner_id.id )
            ship_address = AddressStructure('Address', street, city, zipc, country, region=state)
            eship_from.append( ship_address)

            # line
            line_no = 1
            for line in invoice.invoice_line:
                eline = et.SubElement(einvoice, u"Line")
                et.SubElement(eline, u"LineNumber").text = unicode(line_no)
                line_no+= 1

                # TODO: OrderReferences (optional) referencia à encomenda do cliente
                #eorder_references = et.SubElement(eline, u"OrderReferences")
                #eoriginating_on = et.SubElement(eorder_references, u"OriginatingON")
                #eorder_date = et.SubElement(eorder_references, u"OrderDate")
                #eoriginating_on.text = ''
                #eorder_date.text = ''

                # product code and description
                eproduct_code = et.SubElement(eline, u"ProductCode")
                eproduct_description = et.SubElement(eline, u"ProductDescription")
                if line.product_id:
                    eproduct_code.text = line.product_id.default_code
                    eproduct_description.text = line.product_id.name

                equantity = et.SubElement(eline, u"Quantity")
                if line.quantity:
                    equantity.text = unicode(line.quantity)

                if line.uos_id : # unit of measure (optional)
                    et.SubElement(eline, u"UnitOfMeasure").text=line.uos_id.name
                
                eunit_price = et.SubElement(eline, u"UnitPrice")
                if line.price_unit:
                    eunit_price.text = unicode(line.price_unit)
                if line.price_unit and line.quantity:
                    amount = line.price_unit * line.quantity

                # TODO: TaxPointDate - data do acto gerador do imposto - da entrega ou prestação do serviço
                # usar data da guia de remessa, igual à data usada em ShipTo/DeliveryDate
                etax_point_date = et.SubElement(eline, u"TaxPointDate")
                if invoice.date_invoice:
                    etax_point_date.text = invoice.date_invoice

                # TODO: references (optional)
                ereferences = et.SubElement(eline, u"References")
                ecredit_note = et.SubElement(ereferences, u"CreditNote")
                ereference = et.SubElement(ecredit_note, u"Reference")
                #ereference.text = ''
                ereason = et.SubElement(ecredit_note, u"Reason")
                #ereason.text = ''

                # Description
                et.SubElement(eline, u"Description").text = line.name

                # TODO: debit and credit amount
                debit_amount = credit_amount = 0
                edebit_amount = et.SubElement(eline, u"DebitAmount")
                if invoice.type == 'customer_refund':
                    debit_amount = amount
                edebit_amount.text = unicode(debit_amount)

                total_debit = total_debit + debit_amount

                ecredit_amount = et.SubElement(eline, u"CreditAmount")
                if invoice.type == 'out_invoice' :
                    credit_amount = amount
                ecredit_amount.text = unicode(credit_amount)
                total_credit = total_credit + credit_amount

                # TODO: see invoice_line_tax (optional)
                etax = et.SubElement(eline, u"Tax")
                etax_type = et.SubElement(etax, u"TaxType")
                #etax_type.text = ''
                etax_code = et.SubElement(etax, u"TaxCode")
                #etax_code.text = ''

                # tax percentage
                et.SubElement(etax, u"TaxPercentage").text = line.invoice_line_tax_id and str( line.invoice_line_tax_id[0].amount ) or '0.0'

                # SettlementAmount (optional)
                et.SubElement(eline, u"SettlementAmount").text = str(line.discount )
                # /line

            # document totals
            edocument_totals = et.SubElement(einvoice, u"DocumentTotals")
            etax_payable = et.SubElement(edocument_totals, u"TaxPayable")
            enet_total = et.SubElement(edocument_totals, u"NetTotal")
            egross_total = et.SubElement(edocument_totals, u"GrossTotal")
            
            etax_payable.text = invoice.amount_tax and unicode(invoice.amount_tax) or '0.0'
            enet_total.text = invoice.amount_untaxed and unicode(invoice.amount_untaxed) or '0.0'
            egross_total.text = invoice.amount_total and unicode(invoice.amount_total) or '0.0'

            # TODO currency : only in case of foreign currency (optional)
            if invoice.currency_id.code != 'EUR':
                ecurrency = et.SubElement(edocument_totals, u"Currency")
                ecurrency_code = et.SubElement(ecurrency, u"CurrencyCode")
                #ecurrency_credit_amount = et.SubElement(ecurrency, u"CurrencyCreditAmount")
                #ecurrency_debit_amount = et.SubElement(ecurrency, u"CurrencyDebitAmount")
                ecurrency_code.text = invoice.currency_id.code
                #ecurrency_credit_amount.text = ''
                #ecurrency_debit_amount.text = ''

            # TODO: settlement (optional)
            #esettlement = et.SubElement(edocument_totals, u"Settlement")
            #esettlement_discount = et.SubElement(esettlement, u"SettlementDiscount")
            #esettlement_amount = et.SubElement(esettlement, u"SettlementAmount")
            #esettlement_date = et.SubElement(esettlement, u"SettlementDate")
            #epayment_mechanism = et.SubElement(esettlement, u"PaymentMechanism")
            #esettlement_discount.text = ''
            #esettlement_amount.text = ''
            #esettlement_date.text = ''
            #epayment_mechanism.text = ''

        # totals
        etotal_debit.text = unicode(total_debit)
        etotal_credit.text = unicode(total_credit)
        return esource_documents

wizard_saft()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

