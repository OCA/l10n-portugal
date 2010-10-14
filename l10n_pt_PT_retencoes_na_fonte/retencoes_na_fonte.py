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
# 07/10/2010 - Explicação geral feita por Paulino,
#
# O tratamento das retenções na fonte é obrigatório para uma utilização
# do OpenEPR nas funções facturação e pagamentos.
# Há retenções que são conhecidas logo no momento do registo da factura
#  - as previstas no Cod. IRS nomeadamente - que podem incidir sobre o total
#    ou apenas parte da factura; Outras que só são conhecidas no momento do
#    pagamento;
#  - as retenções por dívidas ao Estado, efectuadas por entidades públicas.
# Em qualquer do casos, o registo na contabilidade tem como referência a data
# do pagamento.
# Os pagamentos das facturas podem ser sujeitos a retenções na fonte.
# Prestadores de serviços em nome individual, por ex. têm as cobranças sujeitas
# a retenção na fonte de 10% de IRS, quando o cliente é uma empresa ou um
# comerciante com contabilidade organizada. As rendas também são sujeitas.
# As vendas de bens não estão sujeitas, apenas as prestações de serviços.
# Implica que numa factura podem coexistir linhas sujeitas a retenção e linhas
# não sujeitas, exemplo:
#  - uma reparação, se estiverem descriminados na factura os materiais/peças
#    consumidos, não sofrem retenção, a mão-de-obra sim.
#    Se os bens integrados no serviço não estiverem descriminados, então a
#    retenção incide sobre o total da factura.
# A retenção é devida no pagamento, o recibo é que deve despoletar o tratamento.
# A informação pode constar nas facturas, mas a titulo meramente informativo.
# Os valores retidos são entregues ao Estado no mês seguinte, no fim do ano é
# entregue uma declaração aos fornecedores aos quais tenham sido efectuadas
# retenções.
# Tem de ser enviada às Finanças uma declaração com o total retido e a base de
# incidência, por NIF e por categoria de rendimentos.
# O mecanismo das retenções pode ser utilizado para tratar as penhoras de
# créditos de fornecedores, por parte das Finanças ou Segurança Social.
#
##############################################################################

from osv import fields
from osv import osv

