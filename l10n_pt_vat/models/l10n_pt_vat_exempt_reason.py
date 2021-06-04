# Copyright (C) 2021 Open Source Integrators (<http://www.opensourceintegrators.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.osv import expression


class VatExemptReason(models.Model):
    _name = "account.l10n_pt.vat.exempt.reason"
    _description = "VAT Exemption Reason"
    _order = "code"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    note = fields.Text(string="Description")

    def name_get(self):
        return [(x.id, "[%s] %s" % (x.code, x.name)) for x in self]

    @api.model
    def _name_search(
        self, name, args=None, operator="ilike", limit=100, name_get_uid=None
    ):
        """
        Returns a list of tuples containing id, name, as internally it is called {def name_get}
        result format: {[(id, name), (id, name), ...]}
        """
        args = args or []
        if operator == "ilike" and not (name or "").strip():
            domain = []
        else:
            connector = "&" if operator in expression.NEGATIVE_TERM_OPERATORS else "|"
            domain = [connector, ("code", operator, name), ("name", operator, name)]
        return self._search(
            expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid
        )
