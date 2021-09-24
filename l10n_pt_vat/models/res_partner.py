# Copyright (C) 2021 Open Source Integrators (https://www.opensourceintegrators.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import api, models


class Partner(models.Model):
    _inherit = "res.partner"

    @api.model
    def vies_vat_check(self, country_code, vat_number):
        """
        The VIES VAT validation service only works for Companies, not for Individual persons.
        (see also proposed bug fix https://github.com/odoo/odoo/pull/76856)
        """
        if country_code == "pt" and self.company_type == "company":
            return self.simple_vat_check(country_code, vat_number)
        else:
            return super().vies_vat_check(country_code, vat_number)
