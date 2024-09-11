from datetime import datetime

import requests

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from .res_company import INVOICE_CREATE


class AbstractMoloni(models.AbstractModel):
    _name = "abstract.moloni"
    _description = "Moloni API"

    moloni_id = fields.Char("Moloni ID")


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "abstract.moloni"]

    def moloni_post(self):
        """Post invoices to Moloni."""
        company = None
        company_id = None
        document_set_id = None
        access_token = None
        product_id = None
        invoice_status = 0

        invoices = self.filtered(lambda i: i.state == "posted" and not i.moloni_id)
        # Sort invoices by company, each time we change company we need to authenticate
        invoices = invoices.sorted(lambda i: i.company_id)

        for invoice in invoices:
            if not company or invoice.company_id.id != company.id:
                company = invoice.company_id

                (
                    company_id,
                    document_set_id,
                    moloni_product_reference,
                ) = company.get_moloni_settings()
                access_token = company.moloni_authenticate()

                # Product
                product_id = company.moloni_get_product_id(
                    access_token, company_id, moloni_product_reference
                )
                if not product_id:
                    product_id = company.moloni_create_product(
                        access_token, company_id, moloni_product_reference
                    )

                # Taxes
                company_invoices = invoices.filtered(
                    lambda i: i.company_id.id == company.id
                )
                taxes = company_invoices.mapped("invoice_line_ids").mapped("tax_ids")
                company.moloni_create_taxes(access_token, company_id, taxes)

                # Draft or close invoice
                invoice_status = company.get_moloni_invoice_status()

            partner = invoice.partner_id

            # Validate if VAT exists
            if not partner.vat:
                raise ValidationError(
                    _("Please configure VAT for customer %s.") % partner.display_name
                )

            # Customer
            customer_id = company.moloni_get_customer_id(
                access_token, company_id, partner
            )
            if customer_id:
                company.moloni_update_customer(
                    access_token, company_id, customer_id, partner
                )
            else:
                customer_id = company.moloni_create_customer(
                    access_token, company_id, partner
                )

            invoice_id = invoice.moloni_create_invoice(
                access_token,
                company_id,
                document_set_id,
                customer_id,
                product_id,
                invoice_status,
            )

            invoice.write({"moloni_id": invoice_id})

    def moloni_create_invoice(
        self,
        access_token,
        company_id,
        document_set_id,
        customer_id,
        product_id,
        invoice_status,
    ):
        """Create invoice."""
        now = datetime.now().date()

        payload = {
            "company_id": company_id,
            "date": now,
            "expiration_date": now,
            "document_set_id": document_set_id,
            "customer_id": customer_id,
            "status": invoice_status,
        }

        for i, line in enumerate(self.invoice_line_ids):
            payload.update(
                {
                    "products[%d][product_id]" % i: product_id,
                    "products[%d][name]" % i: line.name,
                    "products[%d][qty]" % i: line.quantity,
                    "products[%d][price]" % i: line.price_unit,
                }
            )

            if line.discount:
                payload.update(
                    {
                        "products[%d][discount]" % i: line.discount,
                    }
                )

            for j, tax in enumerate(line.tax_ids):
                payload.update(
                    {
                        "products[%d][taxes][%d][tax_id]" % (i, j): tax.moloni_id,
                        "products[%d][taxes][%d][value]" % (i, j): tax.amount,
                        "products[%d][taxes][%d][order]" % (i, j): 1,
                        "products[%d][taxes][%d][cumulative]" % (i, j): 0,
                    }
                )

        r = requests.post(
            INVOICE_CREATE.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Create invoice failed with status code %d.") % r.status_code
            )

        r_json = r.json()

        if (
            not isinstance(r_json, dict)
            or not r_json.get("document_id", False)
            or not r_json.get("valid", False)
        ):
            raise ValidationError(_("Create invoice failed:\n\n%s.") % r_json)

        return r_json["document_id"]


class AccountTax(models.Model):
    _name = "account.tax"
    _inherit = ["account.tax", "abstract.moloni"]
