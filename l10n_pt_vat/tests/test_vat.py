from odoo import fields
from odoo.tests import Form, common


class TestVATPT(common.TransactionCase):
    def setUp(self):
        super().setUp()
        Journal = self.env["account.journal"]
        self.sale_journals = Journal.search([("type", "=", "sale")])
        self.AccountMove = self.env["account.move"]
        self.ResPartner = self.env["res.partner"]
        self.partnerA = self.ResPartner.create(
            {
                "name": "Customer A",
                "country_id": self.pt_country.id,
                "city": "Porto",
                "zip": "2000-555",
            }
        )

    def test_is_vat_enabled_non_pt(self):
        move_form = Form(self.AccountMove.with_context(default_move_type="out_invoice"))
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partnerA
        invoice = move_form.save()
        self.assertFalse(invoice.is_l10npt_vat_enabled)

    def test_is_vat_enabled_pt(self):
        # Ensure Journal is configured
        self.sale_journals.write({"invoicexpress_doc_type": "invoice_receipt"})
        # Create the Invoice
        self.env.company.country_id = self.env.ref("base.pt")
        move_form = Form(self.AccountMove.with_context(default_move_type="out_invoice"))
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partnerA
        invoice = move_form.save()
        self.assertTrue(invoice.is_l10npt_vat_enabled)
