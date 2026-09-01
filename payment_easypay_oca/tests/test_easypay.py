# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from unittest.mock import MagicMock, patch

import requests

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase
from odoo.tools import mute_logger


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
        self.assertEqual(payload["payment"]["methods"], ["card"])
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

        tx._process("easypay", notification_data)
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

        tx._process("easypay", notification_data)
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

        tx._process("easypay", notification_data)
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
        """Test checkout cancel callback sets transaction to canceled."""
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-CANCEL-001",
                "amount": 50.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )

        # Simulate the cancel callback
        response = self.url_open(f"/payment/easypay/checkout/cancel?key={tx.reference}")

        # Verify redirect
        self.assertEqual(response.status_code, 200)

        # Verify transaction was canceled
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "cancel")
