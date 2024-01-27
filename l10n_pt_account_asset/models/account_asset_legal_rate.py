##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014- Sossia, Lda. (<http://www.sossia.pt>)
#    Copyright (C) 2004 OpenERP SA (<http://www.odoo.com>)
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

from openerp import api, fields, models


class AccountAssetLegalRate(models.Model):
    _name = "account.asset.legal_rate"
    _description = "Asset Legal Rate"

    name = fields.Char(string="Name", required=True)

    code = fields.Char(string="Code", size=4, required=True)

    depreciation_rate = fields.Float(
        string="Depreciation rate (%)", default=100.0, digits=(3, 2)
    )

    _sql_constraints = [
        (
            "depreciation_rate",
            " CHECK (depreciation_rate > 0 and depreciation_rate <= 100)",
            "Invalid percentage!",
        ),
    ]

    @api.multi
    @api.depends("name", "code")
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "%s %s" % (rec.code, rec.name)))
        return result

    def name_search(
        self, cr, uid, name, args=None, operator="ilike", context=None, limit=100
    ):
        if args is None:
            args = []
        if context is None:
            context = {}
        ids = []
        if name:
            ids = self.search(cr, uid, [("name", "ilike", name)] + args, limit=limit)
        if not ids:
            ids = self.search(cr, uid, [("code", "ilike", name)] + args, limit=limit)
        return self.name_get(cr, uid, ids, context=context)
