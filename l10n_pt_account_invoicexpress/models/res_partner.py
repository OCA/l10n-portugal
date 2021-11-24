# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _prepare_invoicexpress_vals(self):
        self.ensure_one()
        vals = {
            "name": self.name,
            "email": self.email,
            "address": ", ".join(filter(None, [self.street, self.street2])),
            "city": self.city,
            "postal_code": self.zip,
            "country": self.country_id.invoicexpress_name,
            "fiscal_id": self.vat,
            "website": self.website,
            "phone": self.phone,
        }
        # InvoiceXpress document language (pt, es or rn)
        # Outside PT and ES use english
        # Could be a requirement for some border authorities
        country_code = self.country_id.code
        if country_code == "ES":
            vals["language"] = "es"
        elif country_code == "PT":
            vals["language"] = "pt"
        elif country_code:
            vals["language"] = "en"
        return {k: v for k, v in vals.items() if v}
