# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.tests import common

from .invoicexpress_mock import mock_response


def _mock_set_invoicexpress_contact_request(method, url, **kwargs):
    if method == "GET" and "find-by-code" in url:
        return mock_response({}, status_code=404)
    elif method == "POST" and "clients.json" in url:
        return mock_response({"client": {"id": 999, "name": "Test Partner"}})
    return mock_response({})


@common.tagged("post_install", "-at_install")
class TestResPartnerInvoiceXpress(common.TransactionCase):
    def test_set_invoicexpress_contact_is_company_dependent(self):
        """set_invoicexpress_contact writes the code only for the requested company."""
        main_company = self.env.company
        other_company = self.env["res.company"].create(
            {
                "name": "Other Company",
                "invoicexpress_account_name": "ACCOUNT",
                "invoicexpress_api_key": "APIKEY",
                "country_id": self.env.ref("base.pt").id,
            }
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "country_id": self.env.ref("base.pt").id,
            }
        )

        with patch(
            "requests.request",
            side_effect=_mock_set_invoicexpress_contact_request,
        ):
            partner.set_invoicexpress_contact(company=other_company)

        self.assertEqual(
            partner.with_company(other_company).invoicexpress_code,
            f"ODOO-{partner.id}",
        )
        self.assertFalse(partner.with_company(main_company).invoicexpress_code)
