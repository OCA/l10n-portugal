from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    moloni_developer_id = fields.Char(
        related="company_id.moloni_developer_id", readonly=False
    )
    moloni_client_secret_code = fields.Char(
        related="company_id.moloni_client_secret_code", readonly=False
    )
    moloni_username = fields.Char(related="company_id.moloni_username", readonly=False)
    moloni_password = fields.Char(related="company_id.moloni_password", readonly=False)
    moloni_company_id = fields.Char(
        related="company_id.moloni_company_id", readonly=False
    )
    moloni_invoice_status = fields.Selection(
        related="company_id.moloni_invoice_status", readonly=False
    )
    moloni_document_set_id = fields.Char(
        related="company_id.moloni_document_set_id", readonly=False
    )
    moloni_tax_id = fields.Char(related="company_id.moloni_tax_id", readonly=False)
    moloni_product_reference = fields.Char(
        related="company_id.moloni_product_reference", readonly=False
    )
    moloni_product_category_name = fields.Char(
        related="company_id.moloni_product_category_name", readonly=False
    )
    moloni_product_unit_name = fields.Char(
        related="company_id.moloni_product_unit_name", readonly=False
    )

    def moloni_get_all_companies(self):
        """Show all companies."""
        company = self.env.company
        access_token = company.moloni_authenticate()
        companies = company.moloni_get_all_companies(access_token)

        msg = ""
        for company in companies:
            msg += _("ID: %s\n") % company["company_id"]
            msg += _("Name: %s\n\n") % company["name"]

        raise ValidationError(_("Companies:\n\n%s.") % msg)

    def moloni_get_all_document_sets(self):
        """Show all document sets."""
        company = self.env.company
        company_id = company.get_moloni_company_id()
        access_token = company.moloni_authenticate()
        document_sets = company.moloni_get_all_document_sets(access_token, company_id)

        msg = ""
        for document_set in document_sets:
            msg += _("ID: %s\n") % document_set["document_set_id"]
            msg += _("Name: %s\n\n") % document_set["name"]

        raise ValidationError(_("Document Sets:\n\n%s.") % msg)

    def moloni_get_all_taxes(self):
        """Show all taxes."""
        company = self.env.company
        company_id = company.get_moloni_company_id()
        access_token = company.moloni_authenticate()
        taxes = company.moloni_get_all_taxes(access_token, company_id)

        msg = ""
        for tax in taxes:
            msg += _("ID: %s\n") % tax["tax_id"]
            msg += _("Value: %s\n") % tax["value"]
            msg += _("Name: %s\n\n") % tax["name"]

        raise ValidationError(_("Taxes:\n\n%s.") % msg)
