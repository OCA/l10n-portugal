# -*- encoding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2014- Sossia, Lda. (<http://www.sossia.pt>)
#    Copyright (C) 2004  OpenERP SA (<http://www.odoo.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    "name": "Gestão de Imobilizado para Portugal",
    "version": "0.2",
    "depends": ["account_asset"],
    "author": "Sossia, P. Baeza, "
              "Odoo Community Association (OCA)",
    'summary': 'Implementa os requisitos legais para gestão de Imobilizado',
    "description": """
Gestão de Imobilizado para Portugal
===================================

Este módulo adiciona as funcionalidades necessárias para o cumprimento dos
 requisitos legais e operacionais da gestão de imobilizado, incluindo:

* Alteração do método de cálculo para o prorata temporal.
* Adicionar um novo método de cálculo baseado em percentagem fixa por período
* Adiciona a opção de trasladar a depreciação para o final do período
* Utilização da tabela de taxas legais definidas no DR nº 25/2009

    """,
    "website": "http://www.sossia.pt",
    "category": "Accounting & Finance",
    "data": [
        "security/ir.model.access.csv",
        "views/account_asset_asset.xml",
        "views/account_asset_category.xml",
        "views/account_legal_rate.xml",
        "data/account_legal_rate.xml",
    ],
    "installable": True,
}
