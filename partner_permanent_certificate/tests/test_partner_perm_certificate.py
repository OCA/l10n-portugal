# Copyright 2022 Exo Software (<https://exosoftware.pt>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestPartnerPermCertificate(TransactionCase):
    def setUp(self):
        super(TestPartnerPermCertificate, self).setUp()
        self.main_partner = self.env.ref("base.main_partner")
        self.partner_id_category = self.env.ref(
            "partner_permanent_certificate.id_category_perm_cert"
        )

    def test_01_perm_cert_new(self):
        # Valid new Permanent Certificate Code
        vals = {"name": "0123-4567-8901", "category_id": self.partner_id_category.id}
        self.main_partner.write({"id_numbers": [(0, 0, vals)]})
        perm_cert = self.main_partner.id_numbers[0]

        self.assertEqual(perm_cert.name, "0123-4567-8901")

    def test_02_perm_cert_duplicate(self):
        # Duplicate Permanent Certificate Code
        vals = {"name": "0123-4567-8901", "category_id": self.partner_id_category.id}

        self.main_partner.write({"id_numbers": [(0, 0, vals)]})
        perm_cert = self.main_partner.id_numbers[0].name
        self.assertEqual(perm_cert, "0123-4567-8901")

        new_partner = self.env["res.partner"].create({"name": "Test Partner"})
        new_partner.write({"id_numbers": [(0, 0, vals)]})
        perm_cert = new_partner.id_numbers[0].name
        self.assertEqual(perm_cert, "0123-4567-8901")

    def test_03_perm_cert_create(self):
        new_partner = self.env["res.partner"].create(
            {"name": "Test Partner", "perm_certificate_code": "0123-4567-8901"}
        )

        self.assertEqual(new_partner.perm_certificate_code, "0123-4567-8901")

        id_numbers = new_partner.id_numbers
        self.assertTrue(id_numbers)
        self.assertEqual(len(id_numbers), 1)
        self.assertEqual(id_numbers.name, "0123-4567-8901")

    def test_04_perm_cert_write(self):
        self.main_partner.write({"perm_certificate_code": "0123-4567-8902"})
        perm_cert = self.main_partner.perm_certificate_code
        self.assertEqual(perm_cert, "0123-4567-8902")

        id_numbers = self.main_partner.id_numbers
        self.assertTrue(id_numbers)
        self.assertEqual(len(id_numbers), 1)
        self.assertEqual(id_numbers.name, "0123-4567-8902")
