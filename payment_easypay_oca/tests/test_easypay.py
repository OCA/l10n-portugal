# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import json
from unittest.mock import MagicMock, patch

import requests

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase
from odoo.tools import mute_logger
from odoo.tools.misc import hmac as hmac_tool


@tagged("post_install", "-at_install")
class TestEasyPay(TransactionCase):
    """Test EasyPay payment provider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["payment.provider"].create(
            {
                "name": "EasyPay Test",
                "code": "easypay",
                "state": "test",
                "easypay_account_id": "test-account-id",
                "easypay_api_key": "test-api-key",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "test@example.com",
                "phone": "+351911234567",
            }
        )
        cls.currency = cls.env.ref("base.EUR")
        cls.payment_method = cls.env.ref("payment.payment_method_card")

    def test_provider_creation(self):
        """Test that the provider is created correctly."""
        self.assertEqual(self.provider.code, "easypay")

    def test_api_url_test_mode(self):
        """Test that the correct API URL is returned for test mode."""
        self.provider.state = "test"
        api_url = self.provider._easypay_get_api_url()
        self.assertEqual(api_url, "https://api.test.easypay.pt")

    def test_api_url_production_mode(self):
        """Test that the correct API URL is returned for production mode."""
        self.provider.state = "enabled"
        api_url = self.provider._easypay_get_api_url()
        self.assertEqual(api_url, "https://api.prod.easypay.pt")

    def test_transaction_creation(self):
        """Test that a transaction can be created."""
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-001",
                "amount": 100.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )
        self.assertEqual(tx.provider_code, "easypay")
        self.assertEqual(tx.amount, 100.0)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_create_checkout_session(self, mock_request):
        """Test creating a checkout session with mocked API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "checkout-123",
            "session": "manifest-data",
            "status": "pending",
        }
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-CHECKOUT-001",
                "amount": 100.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )

        result = self.provider._easypay_create_checkout_session(tx.sudo())
        self.assertEqual(result["id"], "checkout-123")
        self.assertEqual(result["session"], "manifest-data")
        self.assertTrue(mock_request.called)

        # Verify the payload sent to EasyPay
        call_args = mock_request.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["type"], ["single"])
        self.assertEqual(payload["payment"]["methods"], ["cc"])
        self.assertEqual(payload["payment"]["currency"], "EUR")
        self.assertEqual(payload["order"]["value"], 100.0)

    def test_notification_processing_success(self):
        """Test processing a successful payment notification."""
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-002",
                "amount": 50.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )

        notification_data = {
            "id": "payment-123",
            "key": "TEST-002",
            "_resolved_status": "paid",
        }

        tx._process_notification_data(notification_data)
        self.assertEqual(tx.state, "done")
        self.assertEqual(tx.provider_reference, "payment-123")

    def test_notification_processing_failed(self):
        """Test processing a failed payment notification."""
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-003",
                "amount": 75.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )

        notification_data = {
            "id": "payment-456",
            "key": "TEST-003",
            "_resolved_status": "failed",
            "message": ["Payment declined"],
        }

        tx._process_notification_data(notification_data)
        self.assertEqual(tx.state, "error")

    def test_notification_processing_authorized(self):
        """Test processing an authorized payment notification."""
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-AUTH-001",
                "amount": 150.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )

        notification_data = {
            "id": "payment-auth-123",
            "key": "TEST-AUTH-001",
            "_resolved_status": "authorised",
            "type": "authorisation",
        }

        tx._process_notification_data(notification_data)
        self.assertEqual(tx.state, "authorized")
        self.assertEqual(tx.provider_reference, "payment-auth-123")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    @mute_logger("odoo.addons.payment_easypay_oca.models.payment_provider")
    def test_http_error_handling(self, mock_request):
        """Test that HTTP errors are properly handled and logged."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": "Invalid payment method",
        }
        mock_response.raise_for_status.side_effect = (
            requests.exceptions.RequestException("400 Bad Request")
        )
        mock_request.return_value = mock_response

        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-ERROR-001",
                "amount": 10.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )

        with self.assertRaises(ValidationError):
            self.provider._easypay_create_checkout_session(tx.sudo())

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_sync_payment_methods_keeps_core_methods_active(self, mock_request):
        """Sync must not deactivate shared core payment methods (card, mb, mbw)
        used by other providers."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"payment_methods": ["vi", "mbw"]}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        card = self.env.ref("payment.payment_method_card")
        mbway = self.env.ref("payment.payment_method_mbway")
        vi = self.env.ref("payment_easypay_oca.payment_method_virtual_iban")
        ap = self.env.ref("payment_easypay_oca.payment_method_apple_pay")
        dd = self.env.ref("payment_easypay_oca.payment_method_easypay_direct_debit")
        # Other enabled providers (e.g. the demo one) may have activated the
        # shared core methods — pin the initial state for determinism.
        card.active = False
        mbway.active = False
        ap.active = True

        self.provider.action_easypay_sync_payment_methods()

        # Shared core methods are never deactivated, but API-returned ones are
        # activated (and linked) so the provider can offer them.
        self.assertFalse(card.active)
        self.assertTrue(mbway.active)
        # Only API-returned methods are linked to the provider. Compare codes,
        # not ids: other addons may register same-code methods (e.g.
        # l10n_pt_payment duplicates core 'mbway').
        self.assertEqual(
            set(self.provider.payment_method_ids.mapped("code")), {"vi", "mbway"}
        )
        # Owned methods not returned are deactivated; dd stays inactive
        self.assertTrue(vi.active)
        self.assertFalse(ap.active)
        self.assertFalse(dd.active)

    def test_processing_values_include_access_token(self):
        """The checkout-session endpoint token is added to processing values."""
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-TOKEN-001",
                "amount": 20.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )
        values = tx._get_processing_values()
        # check_access_token needs an HTTP request; verify the token directly
        # with the same scope and secret used by generate_access_token.
        expected = hmac_tool(self.env(su=True), "generate_access_token", str(tx.id))
        self.assertEqual(values.get("access_token"), expected)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_send_capture_request_polls_until_paid(self, mock_request):
        """Capture resolves the real capture status, not just the API 'ok'."""

        def _api(method, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            if method == "GET":
                resp.json.return_value = {"status": "paid"}
            else:
                resp.json.return_value = {"status": "ok", "id": "cap-1"}
            return resp

        mock_request.side_effect = _api

        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-CAPTURE-001",
                "amount": 30.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )
        tx.provider_reference = "pay-1"
        tx._set_authorized()
        tx._send_capture_request()
        self.assertEqual(tx.state, "done")
        self.assertEqual(tx.easypay_transaction_id, "cap-1")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_send_void_request_success(self, mock_request):
        """A successful void cancels the transaction."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-VOID-001",
                "amount": 40.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )
        tx.provider_reference = "pay-void-1"
        tx._set_authorized()
        tx._send_void_request()
        self.assertEqual(tx.state, "cancel")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_send_void_request_error_keeps_state(self, mock_request):
        """A failed void must not mark the transaction as canceled."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "error",
            "message": ["Void not allowed"],
        }
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-VOID-002",
                "amount": 40.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )
        tx.provider_reference = "pay-void-2"
        tx._set_authorized()
        with self.assertRaises(ValidationError):
            tx._send_void_request()
        self.assertEqual(tx.state, "authorized")


@tagged("post_install", "-at_install")
class TestEasyPayController(HttpCase):
    """Test EasyPay controller endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["payment.provider"].create(
            {
                "name": "EasyPay Test Controller",
                "code": "easypay",
                "state": "test",
                "easypay_account_id": "test-account-id",
                "easypay_api_key": "test-api-key",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner Controller",
                "email": "controller@example.com",
                "phone": "+351911234567",
            }
        )
        cls.currency = cls.env.ref("base.EUR")
        cls.payment_method = cls.env.ref("payment.payment_method_card")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_success_callback(self, mock_request):
        """Test checkout success callback fetches payment data and updates
        transaction.
        """
        # Create transaction with checkout ID
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-SUCCESS-001",
                "amount": 99.99,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
                "easypay_checkout_id": "checkout-success-123",
            }
        )

        # Mock the API response for fetching checkout details
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "checkout-success-123",
            "payment": {
                "id": "payment-success-456",
                "status": "paid",
                "method": "cc",
            },
        }
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        # Simulate the success callback
        response = self.url_open(
            "/payment/easypay/checkout/success"
            "?id=checkout-success-123&key=TEST-SUCCESS-001"
        )

        # Verify redirect to payment status
        self.assertEqual(response.status_code, 200)

        # Verify transaction was updated
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")
        self.assertTrue(mock_request.called)

    def test_checkout_cancel_callback(self):
        """Checkout cancel works via the opaque session_id only — never via
        the guessable transaction reference."""
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-CANCEL-001",
                "amount": 50.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
                "easypay_checkout_id": "checkout-cancel-1",
            }
        )

        # The guessable reference alone must not cancel the transaction
        self.url_open(f"/payment/easypay/checkout/cancel?key={tx.reference}")
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")

        # The opaque session ID cancels it
        self.url_open("/payment/easypay/checkout/cancel?session_id=checkout-cancel-1")
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "cancel")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_webhook_prefers_fetched_status(self, mock_request):
        """A forged 'capture success' webhook must not mark the transaction
        done while the EasyPay API reports it still pending."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"payment": {"status": "pending"}}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-WEBHOOK-001",
                "amount": 60.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
                "easypay_checkout_id": "checkout-wh-1",
            }
        )

        payload = {
            "id": "pay-wh-1",
            "key": tx.reference,
            "type": "capture",
            "status": "success",
        }
        self.url_open(
            "/payment/easypay/webhook/generic",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "pending")

        # When the API confirms the payment, the same webhook marks it done
        mock_response.json.return_value = {"payment": {"status": "paid"}}
        self.url_open(
            "/payment/easypay/webhook/generic",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    @mute_logger("odoo.addons.payment_easypay_oca.controllers.checkout_session")
    def test_checkout_session_requires_access_token(self, mock_request):
        """The checkout-session endpoint rejects requests without a valid
        access token and accepts a valid one."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "checkout-token-1"}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-SESSION-001",
                "amount": 70.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )

        # No token — rejected
        result = self.make_jsonrpc_request(
            "/payment/easypay/create_checkout_session",
            params={"reference": tx.reference},
        )
        self.assertEqual(result.get("error"), "Invalid access token")
        self.assertFalse(tx.easypay_checkout_id)

        # Valid token bound to the transaction — accepted
        token = hmac_tool(self.env(su=True), "generate_access_token", str(tx.id))
        result = self.make_jsonrpc_request(
            "/payment/easypay/create_checkout_session",
            params={"reference": tx.reference, "access_token": token},
        )
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("checkout_id"), "checkout-token-1")
        tx.invalidate_recordset()
        self.assertEqual(tx.easypay_checkout_id, "checkout-token-1")
