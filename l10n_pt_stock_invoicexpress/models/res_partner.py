# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _prepare_invoicexpress_shipping_vals(self):
        self.ensure_one()
        return {
            "email": self.email or "",
            "detail": ", ".join(filter(None, [self.street, self.street2])) or "",
            "city": self.city or "",
            "postal_code": self.zip or "",
            "country": self.country_id.invoicexpress_name or "",
        }
