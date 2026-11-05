from odoo import exceptions, fields
from odoo.tests import Form, common


class TestVATPT(common.TransactionCase):
    def setUp(self):
        super().setUp()
        Journal = self.env["account.journal"]
        self.sale_journals = Journal.search([("type", "=", "sale")])
        self.AccountMove = self.env["account.move"]
        self.ResPartner = self.env["res.partner"]
        self.pt_country = self.env.ref("base.pt")
        self.partnerA = self.ResPartner.create(
            {
                "name": "Customer A",
                "country_id": self.pt_country.id,
                "city": "Porto",
                "zip": "2000-555",
            }
        )
        self.income = self.env["account.account"].create(
            {
                "code": "L10NPTV",
                "name": "Test income",
                "account_type": "income",
            }
        )

    def _new_pt_tax(self, amount):
        tax_group = self.env["account.tax.group"].create(
            {"name": f"IVA {amount}%", "country_id": self.pt_country.id}
        )
        return self.env["account.tax"].create(
            {
                "name": f"IVA {amount}%",
                "amount": amount,
                "type_tax_use": "sale",
                "country_id": self.pt_country.id,
                "tax_group_id": tax_group.id,
            }
        )

    def _new_invoice(self, taxes):
        return self.AccountMove.create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partnerA.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.income.id,
                            "tax_ids": [(6, 0, taxes.ids)],
                        },
                    )
                ],
            }
        )

    def test_is_vat_enabled_non_pt(self):
        move_form = Form(self.AccountMove.with_context(default_move_type="out_invoice"))
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partnerA
        invoice = move_form.save()
        self.assertFalse(invoice.is_l10npt_vat_enabled)

    def test_is_vat_enabled_pt(self):
        self.env.company.account_fiscal_country_id = self.pt_country
        move_form = Form(self.AccountMove.with_context(default_move_type="out_invoice"))
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partnerA
        invoice = move_form.save()
        self.assertTrue(invoice.is_l10npt_vat_enabled)

    def test_post_exempt_tax_requires_reason(self):
        """Posting a PT invoice requires an exemption reason on exempt taxes."""
        self.env.company.account_fiscal_country_id = self.pt_country
        exempt_tax = self._new_pt_tax(0.0)
        invoice = self._new_invoice(exempt_tax)
        invoice.l10npt_vat_exempt_reason = self.env.ref("l10n_pt_account_vat.M07")
        with self.assertRaises(exceptions.ValidationError):
            invoice.action_post()
        exempt_tax.l10n_pt_tax_exemption_reason = "M07"
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

    def test_post_mixed_tax_requires_reason(self):
        """A line mixing a 0% tax with a nonzero tax cannot bypass the check."""
        self.env.company.account_fiscal_country_id = self.pt_country
        exempt_tax = self._new_pt_tax(0.0)
        reduced_tax = self._new_pt_tax(6.0)
        invoice = self._new_invoice(exempt_tax + reduced_tax)
        with self.assertRaises(exceptions.ValidationError):
            invoice.action_post()
        exempt_tax.l10n_pt_tax_exemption_reason = "M07"
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
