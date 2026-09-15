# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestMandateSync(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.env.user.company_id = cls.company.id
        cls.env.user.groups_id |= cls.env.ref(
            "account_payment_order.group_account_payment"
        )
        cls.provider = cls.env["payment.provider"].create(
            {
                "name": "EasyPay Test",
                "code": "easypay",
                "state": "test",
                "company_id": cls.company.id,
                "easypay_account_id": "test-account-id",
                "easypay_api_key": "test-api-key",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "DD Customer",
                "email": "customer@example.com",
                "phone": "+351 911234567",
                "company_id": cls.company.id,
            }
        )
        cls.bank_account = cls.env["res.partner.bank"].create(
            {
                "partner_id": cls.partner.id,
                "acc_number": "PT50 0002 0123 1234 5678 9015 4",
            }
        )
        cls.frequent_response = {
            "status": "ok",
            "id": "freq-uuid-1",
            "method": {
                "type": "dd",
                "status": "active",
                "sdd_mandate": {
                    "id": "m-12345",
                    "iban": "PT50000201231234567890154",
                    "reference_adc": "adc-1",
                },
            },
        }

    def _new_mandate(self, **vals):
        return self.env["account.banking.mandate"].create(
            {
                "format": "easypay",
                "partner_bank_id": self.bank_account.id,
                "signature_date": "2026-01-01",
                "company_id": self.company.id,
                **vals,
            }
        )

    def _mock_api(self, response=None, side_effect=None):
        return patch.object(
            type(self.provider),
            "_easypay_make_request",
            autospec=True,
            return_value=response,
            side_effect=side_effect,
        )

    def test_validate_registers_mandate(self):
        mandate = self._new_mandate()
        with self._mock_api(response=self.frequent_response) as mock_req:
            mandate.validate()
        self.assertEqual(mandate.state, "valid")
        self.assertEqual(mandate.easypay_frequent_id, "freq-uuid-1")
        self.assertEqual(mandate.easypay_mandate_ref, "m-12345")
        self.assertEqual(mandate.easypay_mandate_state, "active")
        self.assertEqual(mandate.easypay_provider_id, self.provider)
        mock_req.assert_called_once()
        args = mock_req.call_args
        self.assertEqual(args.args[1], "/2.0/frequent")
        payload = args.args[2]
        self.assertEqual(payload["method"], "dd")
        self.assertEqual(payload["key"], mandate.unique_mandate_reference)
        self.assertEqual(payload["sdd_mandate"]["iban"], "PT50000201231234567890154")
        self.assertEqual(payload["sdd_mandate"]["email"], "customer@example.com")
        self.assertTrue(payload["sdd_mandate"]["phone"])

    def test_validate_api_error_blocks(self):
        mandate = self._new_mandate()
        with self._mock_api(side_effect=ValidationError("EasyPay API request failed")):
            with self.assertRaises(ValidationError):
                mandate.validate()
        self.assertEqual(mandate.state, "draft")
        self.assertFalse(mandate.easypay_frequent_id)

    def test_validate_status_error_blocks(self):
        mandate = self._new_mandate()
        with self._mock_api(response={"status": "error", "message": ["Invalid IBAN"]}):
            with self.assertRaises(ValidationError):
                mandate.validate()
        self.assertEqual(mandate.state, "draft")

    def test_validate_reuses_token(self):
        token = self.env["payment.token"].create(
            {
                "provider_id": self.provider.id,
                "partner_id": self.partner.id,
                "provider_ref": "freq-existing-1",
                "payment_method_id": self.env.ref(
                    "payment_easypay_oca.payment_method_easypay_direct_debit"
                ).id,
            }
        )
        mandate = self._new_mandate(easypay_token_id=token.id)
        with self._mock_api(response=self.frequent_response) as mock_req:
            mandate.validate()
        mock_req.assert_not_called()
        self.assertEqual(mandate.state, "valid")
        self.assertEqual(mandate.easypay_frequent_id, "freq-existing-1")
        self.assertEqual(mandate.easypay_provider_id, self.provider)

    def test_validate_missing_contact_blocks(self):
        self.partner.email = False
        mandate = self._new_mandate()
        with self._mock_api(response=self.frequent_response) as mock_req:
            with self.assertRaises(UserError):
                mandate.validate()
        mock_req.assert_not_called()
        self.assertEqual(mandate.state, "draft")

    def test_validate_non_easypay_untouched(self):
        mandate = self._new_mandate(format="basic")
        with self._mock_api(response=self.frequent_response) as mock_req:
            mandate.validate()
        mock_req.assert_not_called()
        self.assertEqual(mandate.state, "valid")
