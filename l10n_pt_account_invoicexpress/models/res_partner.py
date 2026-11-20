# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    invoicexpress_code = fields.Char(
        "InvoiceXpress Code",
        copy=False,
        company_dependent=True,
        help="Company-specific identifier used for this partner in InvoiceXpress.",
    )
    invoicexpress_id = fields.Char(
        "InvoiceXpress ID",
        copy=False,
        readonly=True,
        help="Deprecated: will be removed in future versions",
    )

    def _prepare_invoicexpress_vals(self):
        self.ensure_one()
        vals = {
            "name": self.name,
            "code": self.invoicexpress_code,
            "email": self.email,
            "address": ", ".join(filter(None, [self.street, self.street2])),
            "city": self.city,
            "postal_code": self.zip,
            "country": self.country_id.invoicexpress_name,
            "fiscal_id": self.vat,
            "website": self.website,
            "phone": self.phone,
        }
        # InvoiceXpress document language (pt, es or en)
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

    def set_invoicexpress_contact(self, company=False):
        self.ensure_one()
        if self.vat and self.country_id:
            # Double check VAT is right
            vat_prefix, vat_number = self._split_vat(self.vat)
            self._check_vat_number(
                vat_prefix or self.country_id.code.lower(), vat_number
            )
        InvoiceXpress = self.env["account.invoicexpress"]
        company = company or self.company_id or self.env.company
        partner = self.with_company(company)
        doctype = "client"

        if not partner.invoicexpress_code:
            partner.invoicexpress_code = f"ODOO-{partner.ref or partner.id}"
        vals = partner._prepare_invoicexpress_vals()

        # Find existing client by code
        response = InvoiceXpress.call(
            company,
            f"{doctype}s/find-by-code.json",
            "GET",
            params={"client_code": vals["code"]},
            raise_errors=False,
        )
        # Create if missing: POST /clients.json
        if response.status_code == 404:
            response = InvoiceXpress.call(
                company,
                f"{doctype}s.json",
                "POST",
                payload={"client": vals},
            )
        else:
            # Update existing client
            # Check if VAT is the same, if not create a new contact
            values = response.json().get(doctype)
            if values and values.get("fiscal_id") != partner.vat:
                code = partner.invoicexpress_code
                new_code = f"ODOO-{partner.ref or partner.id}-{partner.vat or ''}"
                if code != new_code:
                    partner.invoicexpress_code = new_code
                    return partner.set_invoicexpress_contact(company=company)

            # Update: PUT /clients/$(client-id).json
            client_id = values.get("id")
            response = InvoiceXpress.call(
                company,
                f"{doctype}s/{client_id}.json",
                "PUT",
                payload={"client": vals},
            )

        return {"name": vals["name"], "code": vals["code"]}
