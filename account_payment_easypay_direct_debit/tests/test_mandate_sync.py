# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

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
                "type": "DD",
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
        mandate.action_easypay_prepare_registration()
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
        mandate.action_easypay_prepare_registration()
        with self._mock_api(side_effect=ValidationError("EasyPay API request failed")):
            with self.assertRaises(ValidationError):
                mandate.validate()
        self.assertEqual(mandate.state, "draft")
        self.assertFalse(mandate.easypay_frequent_id)

    def test_validate_status_error_blocks(self):
        mandate = self._new_mandate()
        mandate.action_easypay_prepare_registration()
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

        def _fake_read(_provider, endpoint, payload=None, method="POST", **_kw):
            self.assertEqual(method, "GET")
            self.assertEqual(endpoint, "/2.0/frequent/freq-existing-1")
            return {
                "id": "freq-existing-1",
                "method": self.frequent_response["method"],
            }

        with self._mock_api(side_effect=_fake_read) as mock_req:
            mandate.validate()
        mock_req.assert_called_once()
        self.assertEqual(mock_req.call_args.kwargs.get("method"), "GET")
        self.assertEqual(mandate.state, "valid")
        self.assertEqual(mandate.easypay_frequent_id, "freq-existing-1")
        self.assertEqual(mandate.easypay_provider_id, self.provider)

    def test_validate_token_other_partner_rejected(self):
        """A token granted by another customer cannot back this mandate."""
        other_partner = self.env["res.partner"].create(
            {"name": "Other Customer", "company_id": self.company.id}
        )
        token = self.env["payment.token"].create(
            {
                "provider_id": self.provider.id,
                "partner_id": other_partner.id,
                "provider_ref": "freq-other-1",
                "payment_method_id": self.env.ref(
                    "payment_easypay_oca.payment_method_easypay_direct_debit"
                ).id,
            }
        )
        mandate = self._new_mandate(easypay_token_id=token.id)
        with self._mock_api(response=self.frequent_response) as mock_req:
            with self.assertRaises(UserError):
                mandate.validate()
        mock_req.assert_not_called()
        self.assertEqual(mandate.state, "draft")
        self.assertFalse(mandate.easypay_frequent_id)

    def test_validate_registers_as_accounting_operator(self):
        """A non-admin accounting user registers via the elevated client."""
        operator = new_test_user(
            self.env,
            login="dd_operator",
            groups=(
                "account.group_account_invoice,"
                "account_payment_order.group_account_payment"
            ),
            company_id=self.company.id,
        )
        operator.company_ids = [(4, self.company.id)]
        provider_operator = self.provider.with_user(operator)
        # The API key stays admin-only even though the provider is readable.
        self.assertNotIn("easypay_api_key", provider_operator.fields_get())
        mandate = self._new_mandate().with_user(operator)
        mandate.action_easypay_prepare_registration()
        response = MagicMock()
        response.json.return_value = self.frequent_response
        response.raise_for_status.return_value = None
        with patch("requests.request", return_value=response) as mock_request:
            mandate.validate()
        mock_request.assert_called_once()
        self.assertEqual(mandate.state, "valid")
        self.assertEqual(mandate.easypay_frequent_id, "freq-uuid-1")

    def test_validate_missing_contact_blocks(self):
        """Preparation fails locally — no HTTP call is ever made."""
        self.partner.email = False
        mandate = self._new_mandate()
        with self._mock_api(response=self.frequent_response) as mock_req:
            with self.assertRaises(UserError):
                mandate.action_easypay_prepare_registration()
        mock_req.assert_not_called()
        self.assertEqual(mandate.state, "draft")
        self.assertFalse(mandate.easypay_registration_prepared_at)

    def test_validate_after_registration_window_does_not_post(self):
        """A prepared mandate past its window is never posted to EasyPay."""
        mandate = self._new_mandate()
        mandate.action_easypay_prepare_registration()
        with freeze_time(fields.Datetime.now() + timedelta(hours=24)):
            with self._mock_api(response=self.frequent_response) as mock_req:
                with self.assertRaises(UserError):
                    mandate.validate()
            mock_req.assert_not_called()
        self.assertEqual(mandate.state, "draft")
        self.assertFalse(mandate.easypay_frequent_id)

    def test_validate_recovers_lost_registration(self):
        """An admin recovery ID adopts the remote mandate — one GET, no POST."""
        recovery_id = "123e4567-e89b-42d3-a456-426614174000"
        mandate = self._new_mandate()
        mandate.action_easypay_prepare_registration()
        mandate.easypay_registration_recovery_id = recovery_id

        def _fake_read(_provider, endpoint, payload=None, method="POST", **_kw):
            self.assertEqual(method, "GET")
            self.assertEqual(endpoint, f"/2.0/frequent/{recovery_id}")
            return {
                "id": recovery_id,
                "key": mandate.unique_mandate_reference,
                "method": self.frequent_response["method"],
            }

        with freeze_time(fields.Datetime.now() + timedelta(hours=24)):
            with self._mock_api(side_effect=_fake_read) as mock_req:
                mandate.validate()
        mock_req.assert_called_once()
        self.assertEqual(mock_req.call_args.kwargs.get("method"), "GET")
        self.assertEqual(mandate.state, "valid")
        self.assertEqual(mandate.easypay_frequent_id, recovery_id)
        self.assertEqual(mandate.easypay_mandate_state, "active")
        self.assertFalse(mandate.easypay_registration_recovery_id)

    def test_validate_non_easypay_untouched(self):
        mandate = self._new_mandate(format="basic")
        with self._mock_api(response=self.frequent_response) as mock_req:
            mandate.validate()
        mock_req.assert_not_called()
        self.assertEqual(mandate.state, "valid")
