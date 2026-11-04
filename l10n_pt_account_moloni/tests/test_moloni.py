# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import Mock, patch

import requests

from odoo.tests import common


def mock_response(data, status_code=200):
    response = Mock()
    response.json.return_value = data
    response.text = str(data)
    response.status_code = status_code
    response.content = str(data).encode()
    return response


@common.tagged("-at_install", "post_install")
class TestMoloni(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.write(
            {
                "moloni_client_id": "ID",
                "moloni_client_secret": "SECRET",
                "moloni_username": "USER",
                "moloni_password": "PASS",
                "moloni_company_id": 42,
                "moloni_access_token": "TOKEN",
                "moloni_token_expires_at": "2099-01-01 00:00:00",
                "country_id": self.env.ref("base.pt").id,
            }
        )
        self.journal = self.env["account.journal"].search(
            [("type", "=", "sale")], limit=1
        )
        self.journal.write(
            {
                "l10n_pt_doc_provider": "moloni",
                "moloni_doc_type": "invoices",
            }
        )
        self.partner = self.env["res.partner"].create(
            {"name": "Customer A", "country_id": self.env.ref("base.pt").id}
        )

    @patch.object(requests, "post")
    def test_post_creates_moloni_document(self, mock_post):
        """A posted invoice asks Moloni to insert + finalize the document."""
        mock_post.side_effect = [
            mock_response([{"customer_id": 777}]),  # customers/getByNumber
            mock_response({"customer_id": 777}),  # customers/update
            mock_response({"document_id": 12345678}),  # invoices/insert
            mock_response(
                {
                    "number": "FT 2026/1",
                    "document_id": 12345678,
                }
            ),  # invoices/getOne
            mock_response({}),  # documents/getPdfLink (no url -> skipped)
        ]
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
                "invoice_date": "2026-01-05",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Service",
                            "quantity": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        self.assertEqual(invoice.l10n_pt_doc_type, "invoices")
        self.assertEqual(invoice.l10n_pt_doc_id, "12345678")
        self.assertEqual(invoice.name, "FT 2026/1")
        self.assertEqual(invoice.l10n_pt_doc_number, "FT 2026/1")
