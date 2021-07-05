# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    invoicexpress_id = fields.Char("InvoiceXpress ID", copy=False, readonly=True)

    @api.model
    def _map_invoicexpress_taxes(self, company):
        """
        Retrieves all InvoiceXpress taxes, an maps them
        to the existing Odoo taxes
        """
        InvoiceXpress = self.env["account.invoicexpress"]
        response = InvoiceXpress.call(company, "taxes.json", "GET")
        invx_taxes_dict = {x["name"]: x for x in response.json().get("taxes", [])}
        odoo_taxes = self.search(
            [("type_tax_use", "=", "sale"), ("company_id", "=", company.id)]
        )
        for odoo_tax in odoo_taxes:
            invx_tax_vals = invx_taxes_dict.get(odoo_tax.name)
            if invx_tax_vals:
                odoo_tax._update_invoicexpress_status(invx_tax_vals)

    def _prepare_invoicexpress_vals(self):
        self.ensure_one()
        tax_data = {
            "tax": {
                "name": self.name,
                "value": str(self.amount),
                "region": self.l10n_pt_fiscal_zone or "",
            }
        }
        return tax_data

    def _update_invoicexpress_status(self, result):
        self.invoicexpress_id = result.get("id")

    def action_invoicexpress_tax_create(self):
        InvoiceXpress = self.env["account.invoicexpress"]
        verb = "POST"
        endpoint = "taxes.json"
        for tax in self.filtered(lambda x: not x.invoicexpress_id):
            payload = tax._prepare_invoicexpress_vals()
            response = InvoiceXpress.call(
                tax.company_id, endpoint, verb, payload=payload, raise_errors=False
            )
            if response.status_code == 422:
                # Tax name already exists, map missing invoicexpress_ids
                self._map_invoicexpress_taxes(tax.company_id)
            else:
                InvoiceXpress._check_http_status(response)
                response_json = response.json()
                if "tax" in response_json:
                    tax._update_invoicexpress_status(response_json["tax"])
