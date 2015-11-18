# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2014- Sossia, Lda. (<http://www.sossia.pt>)
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
    "name": "Portugal - IVA",
    "version": "8.0.0.0.3",
    "license": "AGPL-3",
    "depends": ['account', 'base_vat'],
    "author": "Sossia, Odoo Community Association (OCA)",
    "summary": "Portuguese VAT requirements extensions",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Localisation/Europe",
    "data": [
            "security/ir.model.access.csv",
            "data/vat_adjustment_norm.xml",
            "views/vat_adjustment_norm_view.xml",
            "views/account_invoice_view.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
