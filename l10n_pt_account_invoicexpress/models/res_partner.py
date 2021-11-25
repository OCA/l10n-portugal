# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    invoicexpress_id = fields.Char("InvoiceXpress ID", copy=False, readonly=True)

    def _prepare_invoicexpress_vals(self):
        self.ensure_one()
        vals = {
            "name": self.name,
            "code": "ODOO-{}".format(self.ref or self.id),
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

    def set_invoicexpress_contact(self):
        self.ensure_one()
        self.vat and self.check_vat()  # Double check VAT is right
        InvoiceXpress = self.env["account.invoicexpress"]
        company = self.company_id or self.env.company
        doctype = "client"
        vals = self._prepare_invoicexpress_vals()
        invx_id_to_update = self.invoicexpress_id
        if not invx_id_to_update:
            # Create: POST /clients.json
            response = InvoiceXpress.call(
                company,
                "{}s.json".format(doctype),
                "POST",
                payload={"client": vals},
                raise_errors=False,
            )
            if response.status_code == 422:  # Oh, it already exists!
                response = InvoiceXpress.call(
                    company,
                    "{}s/find-by-code.json".format(doctype),
                    "GET",
                    params={"client_code": vals["code"]},
                )
                values = response.json().get(doctype)
                invx_id_to_update = values.get("id")  # Update is needed!
            values = response.json().get(doctype, {})
            self.invoicexpress_id = values.get("id")

        if invx_id_to_update:
            # Update: PUT /clients/$(client-id).json
            response = InvoiceXpress.call(
                company,
                "{}s/{}.json".format(doctype, self.invoicexpress_id),
                "PUT",
                payload={"client": vals},
                raise_errors=True,
            )
        return {"name": vals["name"], "code": vals["code"]}
