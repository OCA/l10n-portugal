# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _prepare_invoicexpress_vals(self):
        self.ensure_one()
        vals = {
            "name": self.name,
            "code": self.vat or "ODOO-{}".format(self.id),
            "email": self.email,
            "address": ", ".join(filter(None, [self.street, self.street2])),
            "city": self.city,
            "postal_code": self.zip,
            "country": self.country_id.invoicexpress_name,
            "language": self.lang[:2],
            "fiscal_id": self.vat,
            "website": self.website,
            "phone": self.phone,
        }
        return {k: v for k, v in vals.items() if v}
