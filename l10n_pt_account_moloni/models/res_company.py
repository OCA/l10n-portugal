import re

import requests

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

AUTH_ENDPOINT = (
    "https://api.moloni.pt/v1/grant/?grant_type=password&client_id={developer_id}"
    "&client_secret={client_secret_code}&username={username}&password={password}"
)
COMPANY_GET_ALL = (
    "https://api.moloni.pt/v1/companies/getAll/?access_token={access_token}"
)
DOCUMENT_SET_GET_ALL = (
    "https://api.moloni.pt/v1/documentSets/getAll/?access_token={access_token}"
)
TAX_GET_ALL = "https://api.moloni.pt/v1/taxes/getAll/?access_token={access_token}"
TAX_CREATE = "https://api.moloni.pt/v1/taxes/insert/?access_token={access_token}"
PRODUCT_SEARCH = (
    "https://api.moloni.pt/v1/products/getByReference/?access_token={access_token}"
)
PRODUCT_CREATE = "https://api.moloni.pt/v1/products/insert/?access_token={access_token}"
PRODUCT_CATEGORY_GET_ALL = (
    "https://api.moloni.pt/v1/productCategories/getAll/?access_token={access_token}"
)
PRODUCT_CATEGORY_CREATE = (
    "https://api.moloni.pt/v1/productCategories/insert/?access_token={access_token}"
)
PRODUCT_UNIT_GET_ALL = (
    "https://api.moloni.pt/v1/measurementUnits/getAll/?access_token={access_token}"
)
PRODUCT_UNIT_CREATE = (
    "https://api.moloni.pt/v1/measurementUnits/insert/?access_token={access_token}"
)
CUSTOMER_SEARCH = (
    "https://api.moloni.pt/v1/customers/getBySearch/?access_token={access_token}"
)
CUSTOMER_NEXT_NUMBER = (
    "https://api.moloni.pt/v1/customers/getNextNumber/?access_token={access_token}"
)
CUSTOMER_CREATE = (
    "https://api.moloni.pt/v1/customers/insert/?access_token={access_token}"
)
CUSTOMER_GET_ONE = (
    "https://api.moloni.pt/v1/customers/getOne/?access_token={access_token}"
)
CUSTOMER_UPDATE = (
    "https://api.moloni.pt/v1/customers/update/?access_token={access_token}"
)
INVOICE_CREATE = "https://api.moloni.pt/v1/invoices/insert/?access_token={access_token}"


class ResCompany(models.Model):
    _inherit = "res.company"

    moloni_developer_id = fields.Char("Developer ID")
    moloni_client_secret_code = fields.Char("Client Secret Code")
    moloni_username = fields.Char("Username")
    moloni_password = fields.Char("Password")
    moloni_company_id = fields.Char("Company ID")
    moloni_invoice_status = fields.Selection(
        [("0", "Draft"), ("1", "Closed")], "Status"
    )
    moloni_document_set_id = fields.Char("Document Set ID")
    moloni_tax_id = fields.Char("Tax ID")
    moloni_product_reference = fields.Char("Product Reference")
    moloni_product_category_name = fields.Char("Product Category Name")
    moloni_product_unit_name = fields.Char("Product Unit Name")

    def get_moloni_company_id(self):
        """Get Moloni company id settings."""
        if not self.moloni_company_id:
            raise ValidationError(
                _("Please configure Moloni company id in invoicing settings.")
            )

        return self.moloni_company_id

    def get_moloni_invoice_status(self):
        """Get Moloni invoice status settings."""
        return int(self.moloni_invoice_status or 0)

    def get_moloni_settings(self):
        """Get Moloni settings."""
        company_id = self.get_moloni_company_id()

        if not self.moloni_document_set_id:
            raise ValidationError(
                _("Please configure Moloni document set id in invoicing settings.")
            )

        if not self.moloni_product_reference:
            raise ValidationError(
                _("Please configure Moloni product reference in invoicing settings.")
            )

        return company_id, self.moloni_document_set_id, self.moloni_product_reference

    def get_moloni_product_settings(self):
        """Get Moloni product settings."""
        if not self.moloni_tax_id:
            raise ValidationError(
                _("Please configure Moloni tax id in invoicing settings.")
            )

        if not self.moloni_product_category_name:
            raise ValidationError(
                _(
                    "Please configure Moloni product category name in invoicing settings."
                )
            )

        if not self.moloni_product_unit_name:
            raise ValidationError(
                _("Please configure Moloni product unit name in invoicing settings.")
            )

        return (
            self.moloni_tax_id,
            self.moloni_product_category_name,
            self.moloni_product_unit_name,
        )

    def moloni_authenticate(self):
        """
        Authenticates in Moloni using the simple method for native applications
        and get access_token if success.
        """
        developer_id = self.moloni_developer_id
        client_secret_code = self.moloni_client_secret_code
        username = self.moloni_username
        password = self.moloni_password

        if not developer_id or not client_secret_code or not username or not password:
            raise ValidationError(
                _(
                    "Please configure Moloni authentication credentials in invoicing settings."
                )
            )

        r = requests.get(
            AUTH_ENDPOINT.format(
                developer_id=developer_id,
                client_secret_code=client_secret_code,
                username=username,
                password=password,
            )
        )

        if r.status_code != 200:
            raise ValidationError(_("Incorrect Moloni authentication credentials."))

        # Valid for 1h
        r_json = r.json()

        access_token = isinstance(r_json, dict) and r_json.get("access_token", False)
        if not access_token:
            raise ValidationError(_("Authentication failed:\n\n%s.") % r_json)

        return access_token

    def moloni_get_all_companies(self, access_token):
        """Get all companies."""
        r = requests.get(COMPANY_GET_ALL.format(access_token=access_token))
        if r.status_code != 200:
            raise ValidationError(
                _("Get all companies failed with status code %d.") % r.status_code
            )

        companies = r.json()

        if not isinstance(companies, list):
            raise ValidationError(_("Get all companies failed:\n\n%s.") % companies)

        return companies

    def moloni_get_all_document_sets(self, access_token, company_id):
        """Get all document sets."""
        payload = {
            "company_id": company_id,
        }

        r = requests.post(
            DOCUMENT_SET_GET_ALL.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Get all document sets failed with status code %d.") % r.status_code
            )

        document_sets = r.json()

        if not isinstance(document_sets, list):
            raise ValidationError(
                _("Get all document sets failed:\n\n%s.") % document_sets
            )

        return document_sets

    def moloni_get_all_taxes(self, access_token, company_id):
        """Get all taxes."""
        payload = {
            "company_id": company_id,
        }

        r = requests.post(TAX_GET_ALL.format(access_token=access_token), data=payload)
        if r.status_code != 200:
            raise ValidationError(
                _("Get all taxes failed with status code %d.") % r.status_code
            )

        taxes = r.json()

        if not isinstance(taxes, list):
            raise ValidationError(_("Get all taxes failed:\n\n%s.") % taxes)

        return taxes

    def moloni_get_product_id(self, access_token, company_id, moloni_product_reference):
        """Check if we have a product with the default product reference."""
        payload = {
            "company_id": company_id,
            "reference": moloni_product_reference,
        }

        r = requests.post(
            PRODUCT_SEARCH.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Search for product failed with status code %d.") % r.status_code
            )

        r_json = r.json()

        return (
            r_json
            and isinstance(r_json[0], dict)
            and r_json[0].get("product_id", False)
        )

    def moloni_create_product(self, access_token, company_id, moloni_product_reference):
        """Create product."""
        (
            moloni_tax_id,
            moloni_product_category_name,
            moloni_product_unit_name,
        ) = self.get_moloni_product_settings()

        payload = {
            "company_id": company_id,
            "category_id": self.get_product_category_id(
                access_token, company_id, moloni_product_category_name
            ),
            "type": 1,
            "name": moloni_product_reference,
            "reference": moloni_product_reference,
            "price": 0.0,
            "unit_id": self.get_product_unit_id(
                access_token, company_id, moloni_product_unit_name
            ),
            "has_stock": False,
            "taxes[0][tax_id]": moloni_tax_id,
            "taxes[0][value]": self.get_tax_value(
                access_token, company_id, moloni_tax_id
            ),
            "taxes[0][order]": 1,
            "taxes[0][cumulative]": 0,
        }

        r = requests.post(
            PRODUCT_CREATE.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Create product failed with status code %d.") % r.status_code
            )

        r_json = r.json()

        if (
            not isinstance(r_json, dict)
            or not r_json.get("product_id", False)
            or not r_json.get("valid", False)
        ):
            raise ValidationError(_("Create product failed:\n\n%s.") % r_json)

        return r_json["product_id"]

    def get_product_category_id(
        self, access_token, company_id, moloni_product_category_name
    ):
        """
        Get product category id.
        Create a new category if one with the default category name doesn't exist.
        """
        payload = {
            "company_id": company_id,
            "parent_id": False,
        }

        # Search for a product category with the name configured on invoice settings
        r = requests.post(
            PRODUCT_CATEGORY_GET_ALL.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Get all product categories failed with status code %d.")
                % r.status_code
            )

        product_categories = r.json()

        if not isinstance(product_categories, list):
            raise ValidationError(
                _("Get all product categories failed:\n\n%s.") % product_categories
            )

        for product_category in product_categories:
            if product_category["name"] == moloni_product_category_name:
                return product_category["category_id"]

        # Create new product category with the name configured on invoice settings
        payload = {
            "company_id": company_id,
            "parent_id": False,
            "name": moloni_product_category_name,
        }

        r = requests.post(
            PRODUCT_CATEGORY_CREATE.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Create product category failed with status code %d.") % r.status_code
            )

        r_json = r.json()

        if (
            not isinstance(r_json, dict)
            or not r_json.get("category_id", False)
            or not r_json.get("valid", False)
        ):
            raise ValidationError(_("Create product category failed:\n\n%s.") % r_json)

        return r_json["category_id"]

    def get_product_unit_id(self, access_token, company_id, moloni_product_unit_name):
        """
        Get product unit id.
        Create a new unit if one with the default category name doesn't exist.
        """
        payload = {
            "company_id": company_id,
        }

        # Search for a product unit with the name configured on invoice settings
        r = requests.post(
            PRODUCT_UNIT_GET_ALL.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Get all product units failed with status code %d.") % r.status_code
            )

        product_units = r.json()

        if not isinstance(product_units, list):
            raise ValidationError(
                _("Get all product units failed:\n\n%s.") % product_units
            )

        for product_unit in product_units:
            if product_unit["name"] == moloni_product_unit_name:
                return product_unit["unit_id"]

        # Create new product unit with the name configured on invoice settings
        payload = {
            "company_id": company_id,
            "name": moloni_product_unit_name,
            "short_name": moloni_product_unit_name,
        }

        r = requests.post(
            PRODUCT_UNIT_CREATE.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Create product unit failed with status code %d.") % r.status_code
            )

        r_json = r.json()

        if (
            not isinstance(r_json, dict)
            or not r_json.get("unit_id", False)
            or not r_json.get("valid", False)
        ):
            raise ValidationError(_("Create product unit failed:\n\n%s.") % r_json)

        return r_json["unit_id"]

    def get_tax_value(self, access_token, company_id, moloni_tax_id):
        """Get tax value."""
        taxes = self.moloni_get_all_taxes(access_token, company_id)

        moloni_tax_id = int(moloni_tax_id)

        for tax in taxes:
            if tax["tax_id"] == moloni_tax_id:
                return tax["value"]

        raise ValidationError(_("Tax with ID %s not found.") % moloni_tax_id)

    def moloni_create_taxes(self, access_token, company_id, taxes):
        """Create taxes."""
        moloni_taxes = self.moloni_get_all_taxes(access_token, company_id)

        for tax in taxes.filtered(lambda t: t.moloni_id):
            self.moloni_check_if_tax_changed(moloni_taxes, tax)

        for tax in taxes.filtered(lambda t: not t.moloni_id):
            self.moloni_create_tax(access_token, company_id, tax)

    def moloni_check_if_tax_changed(self, moloni_taxes, tax):
        """If the tax changed in Moloni, unset moloni id so the tax can be recreated."""
        for moloni_tax in moloni_taxes:
            if moloni_tax["tax_id"] == int(tax.moloni_id):
                if (
                    moloni_tax["name"] != tax.display_name
                    or float_compare(moloni_tax["value"], tax.amount, 2) != 0
                ):
                    tax.write({"moloni_id": False})
                break
        else:
            tax.write({"moloni_id": False})

    def moloni_create_tax(self, access_token, company_id, tax):
        """Create tax."""
        payload = {
            "company_id": company_id,
            "name": tax.display_name,
            "value": tax.amount,
            "type": 1,
            "saft_type": 1,
            "vat_type": "NOR",
            "stamp_tax": False,
            "exemption_reason": False,
            "fiscal_zone": "PT",
            "active_by_default": 1,
        }

        r = requests.post(TAX_CREATE.format(access_token=access_token), data=payload)
        if r.status_code != 200:
            raise ValidationError(
                _("Create tax failed with status code %d.") % r.status_code
            )

        r_json = r.json()

        if (
            not isinstance(r_json, dict)
            or not r_json.get("tax_id", False)
            or not r_json.get("valid", False)
        ):
            raise ValidationError(_("Create tax failed:\n\n%s.") % r_json)

        tax.write({"moloni_id": r_json["tax_id"]})

    def moloni_get_customer_id(self, access_token, company_id, partner):
        """
        Check if we have a customer with the required VAT already created in Moloni.
        If the customer already has an invoice, VAT change is not possible in Moloni
        and it will throw an error silently.
        """
        payload = {
            "company_id": company_id,
            "search": partner.vat,
        }

        r = requests.post(
            CUSTOMER_SEARCH.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Search for customer failed with status code %d.") % r.status_code
            )

        r_json = r.json()

        return (
            r_json
            and isinstance(r_json[0], dict)
            and r_json[0].get("customer_id", False)
        )

    def moloni_update_customer(self, access_token, company_id, customer_id, partner):
        """Update customer."""
        payload = {
            "company_id": company_id,
            "customer_id": customer_id,
        }

        r = requests.post(
            CUSTOMER_GET_ONE.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Get customer failed with status code %d.") % r.status_code
            )

        customer = r.json()

        if not isinstance(customer, dict) or not customer.get("name", False):
            raise ValidationError(_("Get customer failed:\n\n%s.") % customer)

        payload = {
            "company_id": company_id,
            "customer_id": customer_id,
            "vat": partner.vat,
            "number": customer["number"],
            "name": partner.display_name,
            "language_id": customer["language_id"],
            "address": self.moloni_get_partner_address(partner),
            "zip_code": self.moloni_get_partner_zip_code(partner),
            "city": partner.city or customer["city"],
            "country_id": customer["country_id"],
            "email": self.moloni_get_partner_email(partner),
            "maturity_date_id": customer["maturity_date_id"],
            "payment_method_id": customer["payment_method_id"],
        }

        r = requests.post(
            CUSTOMER_UPDATE.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Update customer failed with status code %d.") % r.status_code
            )

        r_json = r.json()

        if (
            not isinstance(r_json, dict)
            or not r_json.get("customer_id", False)
            or not r_json.get("valid", False)
        ):
            raise ValidationError(_("Update customer failed:\n\n%s.") % r_json)

    def moloni_create_customer(self, access_token, company_id, partner):
        """Create customer."""
        payload = {
            "company_id": company_id,
            "vat": partner.vat,
            "number": self.moloni_get_next_customer_number(access_token, company_id),
            "name": partner.display_name,
            "language_id": 1,
            "address": self.moloni_get_partner_address(partner),
            "zip_code": self.moloni_get_partner_zip_code(partner),
            "city": partner.city or "",
            "country_id": 1,
            "email": self.moloni_get_partner_email(partner),
            "maturity_date_id": False,
            "payment_method_id": False,
            "salesman_id": False,
            "payment_day": False,
            "discount": False,
            "credit_limit": False,
            "delivery_method_id": False,
        }

        r = requests.post(
            CUSTOMER_CREATE.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Create customer failed with status code %d.") % r.status_code
            )

        r_json = r.json()

        if (
            not isinstance(r_json, dict)
            or not r_json.get("customer_id", False)
            or not r_json.get("valid", False)
        ):
            raise ValidationError(_("Create customer failed:\n\n%s.") % r_json)

        return r_json["customer_id"]

    def moloni_get_partner_address(self, partner):
        """Get partner address."""
        address = ""
        if partner.street:
            address = partner.street
        if partner.street2:
            if address:
                address += ", "
            address += partner.street2
        return address

    def moloni_get_partner_zip_code(self, partner):
        """Return partner zip code."""
        if partner.zip:
            pattern = re.compile(r"^\d{4}-\d{3}?$")
            return pattern.match(partner.zip) and partner.zip or ""
        return ""

    def moloni_get_partner_email(self, partner):
        """Return partner email."""
        if partner.email:
            pattern = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
            return pattern.match(partner.email) and partner.email or ""
        return ""

    def moloni_get_next_customer_number(self, access_token, company_id):
        """Returns the next available customer number."""
        payload = {
            "company_id": company_id,
        }

        r = requests.post(
            CUSTOMER_NEXT_NUMBER.format(access_token=access_token), data=payload
        )
        if r.status_code != 200:
            raise ValidationError(
                _("Get next customer number failed with status code %d.")
                % r.status_code
            )

        r_json = r.json()

        if not isinstance(r_json, dict) or not r_json.get("number", False):
            raise ValidationError(_("Get next customer number failed:\n\n%s.") % r_json)

        return r_json["number"]
