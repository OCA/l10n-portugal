# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    moloni_code = fields.Char(company_dependent=True, copy=False)

    def _prepare_moloni_vals(self):
        self.ensure_one()
        if not self.moloni_code:
            self.moloni_code = f"ODOO-{self.ref or self.id}"
        return {
            "vat": self.vat or "",
            "number": self.moloni_code,
            "name": self.name,
            "language_id": 1,  # Portuguese
            "address": f"{self.street or ''} {self.street2 or ''}".strip(),
            "zip_code": self.zip or "",
            "city": self.city or "",
            "country_id": 1,  # FIXME resolve Moloni country id (1=Portugal)
            "maturity_date_id": 0,
            "payment_method_id": 0,
            "delivery_method_id": 0,
        }

    def set_moloni_contact(self, company):
        self.ensure_one()
        Moloni = self.env["account.moloni"]
        vals = self._prepare_moloni_vals()
        response = Moloni.call(
            company,
            "customers/getByNumber",
            payload={"company_id": company.moloni_company_id, "number": vals["number"]},
            raise_errors=False,
        )
        customer = (response.json() or [{}])[0] if response.status_code == 200 else {}
        if customer.get("customer_id"):
            vals["customer_id"] = customer["customer_id"]
            Moloni.call(
                company,
                "customers/update",
                payload=dict(vals, company_id=company.moloni_company_id),
            )
            return customer["customer_id"]
        data = Moloni.call(
            company,
            "customers/insert",
            payload=dict(vals, company_id=company.moloni_company_id),
        )
        return data.get("customer_id")
