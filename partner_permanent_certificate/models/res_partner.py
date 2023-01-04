# Copyright 2022 Exo Software (<https://exosoftware.pt>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    perm_certificate_code = fields.Char(
        string="Permanent Certificate Code",
        compute=lambda s: s._compute_identification("perm_certificate_code", "ccp"),
        inverse=lambda s: s._inverse_identification("perm_certificate_code", "ccp"),
        search=lambda s, *a: s._search_identification("ccp", *a),
    )
