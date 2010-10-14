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
# Toda a informação legal, FAQ, schema e aplicações para validação dos ficheiros,
# encontra-se disponível em:
#  * http://info.portaldasfinancas.gov.pt/pt/apoio_contribuinte/NEWS_SAF-T_PT.htm
#
# A versão anterior do modulo saft para OpenERP não contempla a logística - notas
# de encomenda que originam a factura; documentos de transporte; Locais e datas
# de expedição e de recepção dos bens.
# Para tratar esta informação, o OpenERP precisa de instalar alguns modulos
# adicionais - ex: delivery.
# Provavelmente precisamos de repartir a funcionalidade do saft por dois módulos:
#  * módulo base que depende de ''account'' e ''product'' - corresponde à versão
#    de 2009 (precisa ser actualizada para atender à certificação);
#  * modulo estendido, que depende de ''delivery'' (e mais algum ...) e apresenta
#    a totalidade da informação exigível pelo saft. Assim quem não vai usar o
#    modulo ''delivery'' não tem de o instalar para ter o saft.
# Os dados tratados na versão estendida só são obrigatórios se a informação
# existir no sistema.
#
##############################################################################

from osv import fields
from osv import osv

