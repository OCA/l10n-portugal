# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import html
import json
import os
import re
from datetime import date, timedelta
from unittest import SkipTest
from unittest.mock import MagicMock, patch
from urllib.parse import quote, urlsplit
from uuid import uuid4

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
        mock_response.json.return_value = {
            "payment_methods": ["vi", "mbw", "dd", "sepa_direct_debit"],
        }
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        card = self.env.ref("payment.payment_method_card")
        mbway = self.env.ref("payment.payment_method_mbway")
        vi = self.env.ref("payment_easypay_oca.payment_method_virtual_iban")
        ap = self.env.ref("payment_easypay_oca.payment_method_apple_pay")
        dd = self.env.ref("payment_easypay_oca.payment_method_easypay_direct_debit")
        # A shared core method that is already linked and active must stay
        # active: sync never deactivates methods owned by other providers.
        self.provider.payment_method_ids |= card
        card.active = True
        mbway.active = False
        ap.active = True

        other = self.provider.copy({"name": "Another EasyPay Account", "state": "test"})
        other.payment_method_ids = ap

        self.provider.action_easypay_sync_payment_methods()

        # Shared core methods are never deactivated, but API-returned ones are
        # activated (and linked) so the provider can offer them.
        self.assertTrue(card.active)
        self.assertTrue(mbway.active)
        # Only API-returned methods are linked to the provider. Compare codes,
        # not ids: other addons may register same-code methods (e.g.
        # l10n_pt_payment duplicates core 'mbway').
        self.assertEqual(
            set(self.provider.payment_method_ids.mapped("code")), {"vi", "mbway"}
        )
        # Owned methods not returned are deactivated — unless still linked
        # to another provider, like ap on `other`; dd stays inactive.
        self.assertTrue(vi.active)
        self.assertTrue(ap.active)
        self.assertIn(ap, other.payment_method_ids)
        self.assertFalse(dd.active)
        # Direct Debit variants are never synced or linked to the provider.
        self.assertNotIn("dd", self.provider.payment_method_ids.mapped("code"))
        self.assertNotIn(
            "sepa_direct_debit", self.provider.payment_method_ids.mapped("code")
        )

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
        # The checkout-session token is domain-separated from the generic
        # payment access token used by /payment/status and friends.
        expected = hmac_tool(self.env(su=True), "easypay_checkout_session", str(tx.id))
        self.assertEqual(values.get("access_token"), expected)
        self.assertNotEqual(
            values.get("access_token"),
            hmac_tool(self.env(su=True), "generate_access_token", str(tx.id)),
        )

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_send_capture_request_polls_capture_status(self, mock_request):
        """Capture resolves the real capture status, not just the API 'ok'."""

        def _api(method, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            if method == "GET":
                resp.json.return_value = {
                    "id": "cap-1",
                    "transaction_key": "TEST-CAPTURE-001",
                    "payment_id": "pay-1",
                    "value": 30.0,
                    "status": "success",
                }
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
        self.assertEqual(tx.easypay_capture_status, "paid")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_send_capture_request_capture_failed(self, mock_request):
        """A failed capture marks the authorized transaction as error."""

        def _api(method, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            if method == "GET":
                resp.json.return_value = {
                    "id": "cap-fail",
                    "transaction_key": "TEST-CAPTURE-FAIL-001",
                    "payment_id": "pay-fail",
                    "value": 30.0,
                    "status": "failed",
                }
            else:
                resp.json.return_value = {"status": "ok", "id": "cap-fail"}
            return resp

        mock_request.side_effect = _api

        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-CAPTURE-FAIL-001",
                "amount": 30.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )
        tx.provider_reference = "pay-fail"
        tx._set_authorized()
        tx._send_capture_request()
        self.assertEqual(tx.state, "error")
        self.assertEqual(tx.easypay_transaction_id, "cap-fail")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    @patch("odoo.addons.payment_easypay_oca.models.payment_transaction.time.sleep")
    @mute_logger("odoo.addons.payment_easypay_oca.models.payment_transaction")
    def test_send_capture_request_pending_stays_pending(self, mock_sleep, mock_request):
        """A successful capture for the wrong amount cannot settle the order."""

        def _api(method, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            if method == "GET":
                resp.json.return_value = {
                    "id": "cap-pending",
                    "transaction_key": "TEST-CAPTURE-PENDING-001",
                    "payment_id": "pay-pending",
                    "value": 99.0,
                    "status": "success",
                }
            else:
                resp.json.return_value = {"status": "ok", "id": "cap-pending"}
            return resp

        mock_request.side_effect = _api

        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-CAPTURE-PENDING-001",
                "amount": 30.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )
        tx.provider_reference = "pay-pending"
        tx._set_authorized()
        tx._send_capture_request()
        self.assertEqual(tx.state, "pending")
        self.assertEqual(tx.easypay_transaction_id, "cap-pending")
        mock_sleep.assert_called()

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_void_request_stores_id_and_refreshes_status(self, mock_request):
        """A submitted void keeps the authorisation valid until the outcome
        is verified; the stored void id blocks capture and resubmission,
        and a repeat Void click refreshes GET /2.0/void/{id} instead —
        covering a webhook lost before the POST committed. Only verified
        success cancels."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "id": "void-1",
            "message": [],
        }
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
        tx.action_void()
        self.assertEqual(tx.state, "authorized")
        self.assertEqual(tx.easypay_void_id, "void-1")

        # While the outcome is unknown, capture is rejected.
        with self.assertRaises(ValidationError):
            tx.action_capture()

        # A repeat Void click refreshes the stored void's status with a
        # GET — it never resubmits the POST.
        mock_request.reset_mock()
        mock_response.json.return_value = {"id": "void-1", "status": "pending"}
        tx.action_void()
        self.assertEqual(mock_request.call_args.args[0], "GET")
        self.assertTrue(mock_request.call_args.args[1].endswith("/2.0/void/void-1"))
        self.assertEqual(tx.state, "authorized")
        self.assertEqual(tx.easypay_void_id, "void-1")

        # Verified success cancels the transaction — still without any
        # webhook having arrived.
        mock_response.json.return_value = {"id": "void-1", "status": "success"}
        tx.action_void()
        self.assertEqual(tx.state, "cancel")
        self.assertEqual(tx.easypay_void_id, "void-1")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_send_void_request_rejects_missing_void_id(self, mock_request):
        """An 'ok' void response without a void id is rejected: no state
        change and nothing stored."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "message": []}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-VOID-003",
                "amount": 40.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )
        tx.provider_reference = "pay-void-3"
        tx._set_authorized()
        with self.assertRaises(ValidationError):
            tx.action_void()
        self.assertEqual(tx.state, "authorized")
        self.assertFalse(tx.easypay_void_id)

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
            tx.action_void()
        self.assertEqual(tx.state, "authorized")
        self.assertFalse(tx.easypay_void_id)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_idempotency_key_header_on_retryable_post(self, mock_request):
        """The Idempotency-Key header is sent on a retryable POST only when
        a key is provided — letting EasyPay replay the stored response on
        retry instead of processing the request twice."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        self.provider._easypay_make_request(
            "/2.0/capture/payment-id",
            {"value": 10.0},
            idempotency_key="key-123",
        )
        headers = mock_request.call_args.kwargs["headers"]
        self.assertEqual(headers["Idempotency-Key"], "key-123")

        mock_request.reset_mock()
        self.provider._easypay_make_request("/2.0/capture/payment-id", {"value": 10.0})
        headers = mock_request.call_args.kwargs["headers"]
        self.assertNotIn("Idempotency-Key", headers)


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

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _checkout_read(
        checkout_id,
        *,
        payment_id,
        payment_type="single",
        checkout_status="complete",
        payment_status="active",
        methods=None,
        value=60.0,
    ):
        """Authenticated GET /2.0/checkout/{id} payload shape."""
        return {
            "status": "success",
            "message": [],
            "checkout": {"id": checkout_id, "status": checkout_status},
            "payment": {
                "id": payment_id,
                "status": payment_status,
                "type": payment_type,
                "currency": "EUR",
                "methods": ["CC"] if methods is None else methods,
            },
            "value": value,
        }

    @staticmethod
    def _single_read(
        payment_id,
        *,
        value=60.0,
        payment_status="paid",
        method=None,
        captures=None,
        multibanco=None,
    ):
        """Authenticated GET /2.0/single/{id} payload shape."""
        data = {
            "id": payment_id,
            "currency": "EUR",
            "value": value,
            "payment_status": payment_status,
            "method": {"type": "CC"} if method is None else method,
            "captures": [] if captures is None else captures,
        }
        if multibanco is not None:
            data["multibanco"] = multibanco
        return data

    @staticmethod
    def _frequent_read(payment_id, *, method=None):
        """Authenticated GET /2.0/frequent/{id} payload shape.

        The documented response carries no payment_status — the method
        object holds the status instead.
        """
        return {
            "id": payment_id,
            "key": "order-key",
            "currency": "EUR",
            "method": (
                {"type": "CC", "status": "active"} if method is None else method
            ),
            "captures": [],
        }

    @staticmethod
    def _capture_read(
        capture_id, reference, *, payment_id, value=60.0, status="success"
    ):
        """Authenticated GET /2.0/capture/{id} payload shape."""
        return {
            "id": capture_id,
            "transaction_key": reference,
            "value": value,
            "status": status,
            "payment_id": payment_id,
        }

    @staticmethod
    def _api_router(get_reads=None, post_reads=None):
        """requests.request side_effect dispatching EasyPay endpoints."""

        def _api(method, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            table = post_reads if method == "POST" else get_reads
            payload = {}
            for fragment, data in (table or {}).items():
                if fragment in url:
                    payload = data
                    break
            resp.json.return_value = payload
            return resp

        return _api

    def _start_checkout_session(self, tx, checkout_id):
        """Create a checkout session through the real JSON-RPC endpoint."""
        token = tx._get_processing_values()["access_token"]
        result = self.make_jsonrpc_request(
            "/payment/easypay/create_checkout_session",
            params={"reference": tx.reference, "access_token": token},
        )
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("checkout_id"), checkout_id)
        return result

    def _checkout_page_csrf(self, session_id):
        """Render the checkout page and return the CSRF token it carries."""
        response = self.url_open(f"/payment/easypay/checkout?session_id={session_id}")
        self.assertEqual(response.status_code, 200)
        match = re.search(r'data-easypay="([^"]*)"', response.text)
        self.assertIsNotNone(match)
        data = json.loads(html.unescape(match.group(1)))
        return data["csrfToken"]

    def _post_checkout(self, path, session_id, csrf_token, **extra):
        data = {"csrf_token": csrf_token, "session_id": session_id}
        data.update(extra)
        return self.url_open(path, data=data)

    def _checkout_tx(self, reference, amount=60.0, **values):
        values.setdefault("provider_id", self.provider.id)
        values.setdefault("payment_method_id", self.payment_method.id)
        values.setdefault("currency_id", self.currency.id)
        values.setdefault("partner_id", self.partner.id)
        return self.env["payment.transaction"].create(
            {"reference": reference, "amount": amount, **values}
        )

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_multibanco_checkout_uses_configured_expiry(self, mock_request):
        """A Multibanco checkout carries the merchant's reference deadline."""
        self.provider.easypay_mb_expiration_days = 7
        multibanco = self.env.ref("payment.payment_method_multibanco")
        tx = self._checkout_tx("TEST-MB-EXPIRY", payment_method_id=multibanco.id)
        checkout_id = "checkout-mb-expiry"
        mock_request.side_effect = self._api_router(
            post_reads={"/2.0/checkout": {"id": checkout_id, "session": "manifest"}},
        )
        day_before = date.today()
        self._start_checkout_session(tx, checkout_id)
        day_after = date.today()
        payload = mock_request.call_args.kwargs["json"]
        self.assertNotIn("multibanco", payload)
        self.assertEqual(payload["payment"]["methods"], ["mb"])
        self.assertIn(
            payload["payment"]["multibanco"]["expiration_time"],
            {
                f"{day + timedelta(days=7):%Y-%m-%d}T23:59:59Z"
                for day in (day_before, day_after)
            },
        )

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_frequent_multibanco_checkout_omits_single_payment_settings(
        self, mock_request
    ):
        """Frequent checkout sends the method without single-payment expiry settings."""
        multibanco = self.env.ref("payment.payment_method_multibanco")
        tx = self._checkout_tx(
            "TEST-MB-FREQUENT", payment_method_id=multibanco.id, tokenize=True
        )
        checkout_id = "checkout-mb-frequent"
        mock_request.side_effect = self._api_router(
            post_reads={"/2.0/checkout": {"id": checkout_id, "session": "manifest"}},
        )
        self._start_checkout_session(tx, checkout_id)
        payload = mock_request.call_args.kwargs["json"]
        self.assertEqual(payload["type"], ["frequent"])
        self.assertEqual(payload["payment"]["methods"], ["mb"])
        self.assertNotIn("multibanco", payload)
        self.assertNotIn("multibanco", payload["payment"])

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_success_callback(self, mock_request):
        """A verified paid checkout marks the transaction done; SDK fields
        sent by the browser are never trusted."""
        tx = self._checkout_tx("TEST-SUCCESS-001", amount=99.99)
        checkout_id = "chk-succ-1"
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {
                    "id": checkout_id,
                    "session": "manifest",
                    "status": "pending",
                }
            },
            get_reads={
                "/checkout/": self._checkout_read(
                    checkout_id, payment_id="pay-succ-1", value=99.99
                ),
                "/single/": self._single_read(
                    "pay-succ-1",
                    value=99.99,
                    method={
                        "type": "CC",
                        "card_type": "VISA",
                        "last_four": "4242",
                    },
                    captures=[
                        {
                            "id": "cap-succ-1",
                            "status": "success",
                            "transaction_key": tx.reference,
                        }
                    ],
                ),
                "/frequent/": {},
                "/capture/": self._capture_read(
                    "cap-succ-1",
                    tx.reference,
                    payment_id="pay-succ-1",
                    value=99.99,
                ),
            },
        )
        self._start_checkout_session(tx, checkout_id)
        csrf_token = self._checkout_page_csrf(checkout_id)

        response = self._post_checkout(
            "/payment/easypay/checkout/success",
            checkout_id,
            csrf_token,
            # Forged SDK fields must be ignored entirely.
            method="MB",
            entity="99999",
            mb_reference="000000000",
            payment_id="forged-payment",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("/payment/status", response.url)

        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")
        self.assertEqual(tx.provider_reference, "pay-succ-1")
        self.assertEqual(tx.easypay_transaction_id, "cap-succ-1")
        self.assertEqual(tx.easypay_payment_method, "cc")
        self.assertFalse(tx.easypay_mb_entity)
        self.assertFalse(tx.easypay_mb_reference)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_success_multibanco_uses_authenticated_details(self, mock_request):
        """MB entity/reference/expiration come only from the authenticated
        EasyPay read — never from the callback request — and the customer
        lands on the protected reference page while pending."""
        tx = self._checkout_tx("TEST-MB-001")
        checkout_id = "chk-mb-1"
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {
                    "id": checkout_id,
                    "session": "manifest",
                    "status": "pending",
                }
            },
            get_reads={
                "/checkout/": self._checkout_read(
                    checkout_id,
                    payment_id="pay-mb-1",
                    methods=["MB"],
                ),
                "/single/": self._single_read(
                    "pay-mb-1",
                    payment_status="pending",
                    method={
                        "type": "MB",
                        "entity": "11683",
                        "reference": "665876931",
                    },
                    multibanco={"expiration_time": "2026-01-01T23:59:59Z"},
                ),
                "/frequent/": {},
            },
        )
        self._start_checkout_session(tx, checkout_id)
        csrf_token = self._checkout_page_csrf(checkout_id)

        response = self._post_checkout(
            "/payment/easypay/checkout/success",
            checkout_id,
            csrf_token,
            entity="FORGED-ENTITY",
            mb_reference="FORGED-REF",
            expiration="FORGED-EXPIRATION",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("/payment/easypay/mb_reference/", response.url)

        tx.invalidate_recordset()
        self.assertEqual(tx.state, "pending")
        self.assertEqual(tx.provider_reference, "pay-mb-1")
        self.assertEqual(tx.easypay_mb_entity, "11683")
        self.assertEqual(tx.easypay_mb_reference, "665876931")
        self.assertEqual(tx.easypay_mb_expiration, "2026-01-01T23:59:59Z")
        # The protected page rendered the authenticated reference.
        self.assertIn("11683", response.text)
        self.assertIn("665 876 931", response.text)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_success_pending_non_mb_redirects_to_status(self, mock_request):
        """An in-flight non-MB payment (e.g. MB WAY) ends pending on the
        generic status page."""
        tx = self._checkout_tx("TEST-MBW-001")
        checkout_id = "chk-mbw-1"
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {
                    "id": checkout_id,
                    "session": "manifest",
                    "status": "pending",
                }
            },
            get_reads={
                "/checkout/": self._checkout_read(
                    checkout_id,
                    payment_id="pay-mbw-1",
                    methods=["MBW"],
                    payment_status="pending",
                ),
                "/single/": self._single_read(
                    "pay-mbw-1",
                    payment_status="pending",
                    method={"type": "MBW", "alias": "79cb81f6"},
                ),
                "/frequent/": {},
            },
        )
        self._start_checkout_session(tx, checkout_id)
        csrf_token = self._checkout_page_csrf(checkout_id)

        response = self._post_checkout(
            "/payment/easypay/checkout/success", checkout_id, csrf_token
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("/payment/status", response.url)

        tx.invalidate_recordset()
        self.assertEqual(tx.state, "pending")
        self.assertEqual(tx.provider_reference, "pay-mbw-1")
        self.assertFalse(tx.easypay_mb_entity)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_success_frequent_tokenizes_and_captures(self, mock_request):
        """A verified frequent checkout creates the token and captures the
        initial amount using only authenticated reads."""
        tx = self._checkout_tx("TEST-FREQ-001", tokenize=True)
        checkout_id = "chk-freq-1"
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {
                    "id": checkout_id,
                    "session": "manifest",
                    "status": "pending",
                },
                "/capture/": {"status": "ok", "id": "cap-freq-1", "message": []},
            },
            get_reads={
                "/checkout/": self._checkout_read(
                    checkout_id,
                    payment_id="pay-freq-1",
                    payment_type="frequent",
                    payment_status="active",
                ),
                "/single/": {},
                "/frequent/": self._frequent_read(
                    "pay-freq-1",
                    method={
                        "type": "CC",
                        "status": "active",
                        "card_type": "VISA",
                        "last_four": "0000",
                        "expiration_date": "04/25",
                    },
                ),
                "/capture/": self._capture_read(
                    "cap-freq-1", tx.reference, payment_id="pay-freq-1"
                ),
            },
        )
        self._start_checkout_session(tx, checkout_id)
        csrf_token = self._checkout_page_csrf(checkout_id)

        response = self._post_checkout(
            "/payment/easypay/checkout/success", checkout_id, csrf_token
        )
        self.assertEqual(response.status_code, 200)

        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")
        self.assertTrue(tx.token_id)
        self.assertEqual(tx.provider_reference, "pay-freq-1")
        self.assertEqual(tx.easypay_transaction_id, "cap-freq-1")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_saved_card_webhook_completes_without_browser_return(self, mock_request):
        """A customer can save a card and pay even if the browser never returns."""
        tx = self._checkout_tx("TEST-FREQUENT-NO-RETURN", tokenize=True)
        checkout_id, payment_id, capture_id = (
            "chk-web-freq",
            "pay-web-freq",
            "cap-web-freq",
        )
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {"id": checkout_id, "session": "manifest"},
                "/capture/": {"status": "ok", "id": capture_id},
            },
            get_reads={
                "/checkout/": self._checkout_read(
                    checkout_id,
                    payment_id=payment_id,
                    payment_type="frequent",
                    payment_status="tokenized",
                ),
                "/frequent/": self._frequent_read(payment_id),
                "/capture/": self._capture_read(
                    capture_id, tx.reference, payment_id=payment_id
                ),
            },
        )
        self._start_checkout_session(tx, checkout_id)
        csrf_token = self._checkout_page_csrf(checkout_id)
        event = {
            "id": payment_id,
            "key": tx.reference,
            "type": "frequent_create",
            "status": "success",
        }
        response = self._post_webhook(dict(event, id="unrelated-payment"))
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertFalse(tx.token_id)
        self.assertFalse(tx.easypay_transaction_id)
        response = self._post_webhook(event)
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")
        self.assertTrue(tx.token_id)
        self.assertEqual(tx.easypay_transaction_id, capture_id)
        saved_token = tx.token_id
        self.assertEqual(self._post_webhook(event).status_code, 200)
        self.assertEqual(
            self._post_checkout(
                "/payment/easypay/checkout/success", checkout_id, csrf_token
            ).status_code,
            200,
        )
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")
        self.assertEqual(tx.token_id, saved_token)
        self.assertEqual(tx.easypay_transaction_id, capture_id)
        captures = [
            c
            for c in mock_request.call_args_list
            if c.args[:2]
            == ("POST", f"https://api.test.easypay.pt/2.0/capture/{payment_id}")
        ]
        self.assertEqual(len(captures), 1)
        self.assertTrue(captures[0].kwargs["headers"].get("Idempotency-Key"))
        [checkout_call] = [
            c
            for c in mock_request.call_args_list
            if c.args[0] == "POST" and c.args[1].endswith("/2.0/checkout")
        ]
        self.assertEqual(checkout_call.kwargs["json"]["payment"]["key"], tx.reference)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_saved_card_webhook_retries_capture_without_id(self, mock_request):
        """A capture acknowledgement without an ID is retried, not committed."""
        tx = self._checkout_tx("TEST-FREQUENT-CAPTURE-RETRY", tokenize=True)
        checkout_id, payment_id, capture_id = (
            "chk-web-freq-retry",
            "pay-web-freq-retry",
            "cap-web-freq-retry",
        )
        capture_ack = {"status": "ok"}
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {"id": checkout_id, "session": "manifest"},
                "/capture/": capture_ack,
            },
            get_reads={
                "/checkout/": self._checkout_read(
                    checkout_id,
                    payment_id=payment_id,
                    payment_type="frequent",
                    payment_status="tokenized",
                ),
                "/frequent/": self._frequent_read(payment_id),
                "/capture/": self._capture_read(
                    capture_id, tx.reference, payment_id=payment_id
                ),
            },
        )
        self._start_checkout_session(tx, checkout_id)
        event = {
            "id": payment_id,
            "key": tx.reference,
            "type": "frequent_create",
            "status": "success",
        }
        response = self._post_webhook(event)
        self.assertEqual(response.status_code, 503)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")
        self.assertFalse(tx.token_id)
        self.assertFalse(tx.easypay_transaction_id)
        capture_ack["id"] = capture_id
        response = self._post_webhook(event)
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")
        self.assertTrue(tx.token_id)
        self.assertEqual(tx.easypay_transaction_id, capture_id)
        captures = [
            c
            for c in mock_request.call_args_list
            if c.args[:2]
            == ("POST", f"https://api.test.easypay.pt/2.0/capture/{payment_id}")
        ]
        self.assertEqual(len(captures), 2)
        keys = {c.kwargs["headers"].get("Idempotency-Key") for c in captures}
        self.assertEqual(len(keys), 1)
        self.assertTrue(next(iter(keys)))

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_success_frequent_inactive_method_is_ignored(self, mock_request):
        """A completed frequent checkout whose method is not active yet
        (e.g. pending confirmation) must not create a token or capture —
        the webhook finishes the job later."""
        tx = self._checkout_tx("TEST-FREQ-PENDING-001", tokenize=True)
        checkout_id = "chk-freq-pending-1"
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {
                    "id": checkout_id,
                    "session": "manifest",
                    "status": "pending",
                }
            },
            get_reads={
                "/checkout/": self._checkout_read(
                    checkout_id,
                    payment_id="pay-freq-pending-1",
                    payment_type="frequent",
                    payment_status="active",
                ),
                "/single/": {},
                "/frequent/": self._frequent_read(
                    "pay-freq-pending-1",
                    method={"type": "CC", "status": "pending"},
                ),
            },
        )
        self._start_checkout_session(tx, checkout_id)
        csrf_token = self._checkout_page_csrf(checkout_id)

        response = self._post_checkout(
            "/payment/easypay/checkout/success", checkout_id, csrf_token
        )
        self.assertEqual(response.status_code, 200)

        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")
        self.assertFalse(tx.token_id)
        self.assertFalse(tx.provider_reference)
        self.assertFalse(tx.easypay_transaction_id)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_success_without_verified_checkout_is_ignored(self, mock_request):
        """When the authenticated checkout read fails, the callback changes
        nothing — no token, no reference, no state."""
        tx = self._checkout_tx("TEST-GHOST-001")
        checkout_id = "chk-ghost-1"
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {
                    "id": checkout_id,
                    "session": "manifest",
                    "status": "pending",
                }
            },
            get_reads={"/checkout/": {}},
        )
        self._start_checkout_session(tx, checkout_id)
        csrf_token = self._checkout_page_csrf(checkout_id)

        response = self._post_checkout(
            "/payment/easypay/checkout/success", checkout_id, csrf_token
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("/payment/status", response.url)

        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")
        self.assertFalse(tx.provider_reference)
        self.assertFalse(tx.easypay_payment_details)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_success_without_verified_payment_is_ignored(self, mock_request):
        """A verified checkout without verified payment details leaves the
        transaction untouched — webhooks finish the job."""
        tx = self._checkout_tx("TEST-NOSINGLE-001")
        checkout_id = "chk-nosingle-1"
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {
                    "id": checkout_id,
                    "session": "manifest",
                    "status": "pending",
                }
            },
            get_reads={
                "/checkout/": self._checkout_read(
                    checkout_id, payment_id="pay-nosingle-1"
                ),
                "/single/": {},
                "/frequent/": {},
            },
        )
        self._start_checkout_session(tx, checkout_id)
        csrf_token = self._checkout_page_csrf(checkout_id)

        response = self._post_checkout(
            "/payment/easypay/checkout/success", checkout_id, csrf_token
        )
        self.assertEqual(response.status_code, 200)

        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")
        self.assertFalse(tx.provider_reference)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_success_rejects_session_not_owned(self, mock_request):
        """A session id that is not the one stored in this browser session
        cannot touch another transaction — and no provider read happens."""
        owned_tx = self._checkout_tx("TEST-OWNED-001")
        checkout_id = "chk-owned-1"
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {
                    "id": checkout_id,
                    "session": "manifest",
                    "status": "pending",
                }
            },
        )
        self._start_checkout_session(owned_tx, checkout_id)
        csrf_token = self._checkout_page_csrf(checkout_id)

        orphan_tx = self._checkout_tx(
            "TEST-ORPHAN-001", easypay_checkout_id="chk-orphan-1"
        )
        response = self._post_checkout(
            "/payment/easypay/checkout/success",
            "chk-orphan-1",
            csrf_token,
        )
        self.assertEqual(response.status_code, 200)

        orphan_tx.invalidate_recordset()
        owned_tx.invalidate_recordset()
        self.assertEqual(orphan_tx.state, "draft")
        self.assertFalse(orphan_tx.provider_reference)
        self.assertEqual(owned_tx.state, "draft")
        # Only the session-creation POST reached EasyPay; the rejected
        # callback performed no checkout read.
        self.assertEqual(mock_request.call_count, 1)

    def test_checkout_callbacks_are_post_only(self):
        """GET requests can no longer trigger success or cancel processing."""
        tx = self._checkout_tx("TEST-GET-001", easypay_checkout_id="chk-get-1")
        for path in (
            "/payment/easypay/checkout/success",
            "/payment/easypay/checkout/cancel",
        ):
            response = self.url_open(f"{path}?session_id=chk-get-1")
            self.assertEqual(response.status_code, 405)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_retry_reuses_draft_session(self, mock_request):
        """Refreshing a draft checkout cannot start a second payable session."""
        tx = self._checkout_tx("TEST-REUSE-DRAFT")
        checkout_id = "checkout-reuse-draft"
        mock_request.side_effect = self._api_router(
            post_reads={"/2.0/checkout": {"id": checkout_id, "session": "manifest"}}
        )
        self._start_checkout_session(tx, checkout_id)
        self._start_checkout_session(tx, checkout_id)
        calls = [
            c
            for c in mock_request.call_args_list
            if c.args[0] == "POST" and c.args[1].endswith("/2.0/checkout")
        ]
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].kwargs["headers"].get("Idempotency-Key"))

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_cancel_callback(self, mock_request):
        """Only EasyPay can confirm a cancellation: even the browser session
        owning the checkout leaves the draft untouched, and foreign session
        ids or the bare reference never reach the transaction."""
        tx = self._checkout_tx("TEST-CANCEL-001")
        checkout_id = "chk-can-1"
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {
                    "id": checkout_id,
                    "session": "manifest",
                    "status": "pending",
                }
            },
        )
        self._start_checkout_session(tx, checkout_id)
        csrf_token = self._checkout_page_csrf(checkout_id)

        # A foreign session id cannot cancel.
        self._post_checkout(
            "/payment/easypay/checkout/cancel", "chk-other-1", csrf_token
        )
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")

        # Neither can the guessable transaction reference.
        self.url_open(
            "/payment/easypay/checkout/cancel",
            data={"csrf_token": csrf_token, "key": tx.reference},
        )
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")

        # Even the owning browser cannot confirm that EasyPay cancelled the payment.
        self._post_checkout("/payment/easypay/checkout/cancel", checkout_id, csrf_token)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_cancel_keeps_non_draft_transaction(self, mock_request):
        """The browser cancel callback cancels only draft transactions —
        a pending transfer may still settle and Odoo cannot go cancel ->
        done, and an authorized payment is the customer's to keep."""
        tx = self._checkout_tx("TEST-CANCEL-AUTH-001")
        checkout_id = "chk-can-auth-1"
        mock_request.side_effect = self._api_router(
            post_reads={
                "/2.0/checkout": {
                    "id": checkout_id,
                    "session": "manifest",
                    "status": "pending",
                }
            },
        )
        self._start_checkout_session(tx, checkout_id)
        csrf_token = self._checkout_page_csrf(checkout_id)

        tx._set_authorized()
        self._post_checkout("/payment/easypay/checkout/cancel", checkout_id, csrf_token)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "authorized")

        tx._set_pending(extra_allowed_states=("authorized",))
        self._post_checkout("/payment/easypay/checkout/cancel", checkout_id, csrf_token)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "pending")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_webhook_prefers_fetched_status(self, mock_request):
        """A forged 'capture success' webhook must not mark the transaction
        done while the EasyPay API reports it still pending; the verified
        capture status then flips it to done."""
        checkout = {
            "status": "success",
            "checkout": {"id": "checkout-wh-1", "status": "complete"},
            "payment": {
                "id": "pay-wh-1",
                "status": "pending",
                "currency": "EUR",
                "methods": ["CC"],
            },
            "value": 60.0,
        }
        single = {
            "id": "pay-wh-1",
            "currency": "EUR",
            "value": 60.0,
            "payment_status": "pending",
            "method": {"type": "CC"},
            "captures": [
                {
                    "id": "cap-wh-1",
                    "status": "pending",
                    "transaction_key": "TEST-WEBHOOK-001",
                }
            ],
        }
        capture = {
            "id": "cap-wh-1",
            "transaction_key": "TEST-WEBHOOK-001",
            "value": 60.0,
            "status": "pending",
            "payment_id": "pay-wh-1",
        }

        def _api(method, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            if "/checkout/" in url:
                resp.json.return_value = checkout
            elif "/capture/" in url:
                resp.json.return_value = capture
            elif "/single/" in url or "/frequent/" in url:
                resp.json.return_value = single
            else:
                resp.json.return_value = {}
            return resp

        mock_request.side_effect = _api

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
            "key": tx.reference,
            "type": "capture",
            "status": "success",
        }
        response = self._post_webhook(payload)
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        # The event claims success but the verified capture is still pending
        self.assertEqual(tx.state, "pending")
        self.assertEqual(tx.provider_reference, "pay-wh-1")
        self.assertEqual(tx.easypay_transaction_id, "cap-wh-1")

        # Once the authenticated API reports the capture as successful, the
        # same webhook marks the transaction done.
        capture["status"] = "success"
        single["payment_status"] = "paid"
        single["captures"][0]["status"] = "success"
        response = self._post_webhook(payload)
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")

    def _easypay_webhook_fixtures(self, reference="TEST-WEBHOOK-SEC"):
        """Realistic authenticated EasyPay reads for webhook tests."""
        checkout = {
            "status": "success",
            "checkout": {"id": "checkout-wh-1", "status": "complete"},
            "payment": {
                "id": "pay-wh-1",
                "status": "pending",
                "currency": "EUR",
                "methods": ["CC"],
            },
            "value": 60.0,
        }
        single = {
            "id": "pay-wh-1",
            "currency": "EUR",
            "value": 60.0,
            "payment_status": "pending",
            "method": {"type": "CC"},
            "captures": [
                {
                    "id": "cap-wh-1",
                    "status": "pending",
                    "transaction_key": reference,
                }
            ],
        }
        capture = {
            "id": "cap-wh-1",
            "transaction_key": reference,
            "value": 60.0,
            "status": "pending",
            "payment_id": "pay-wh-1",
        }
        return checkout, single, capture

    def _easypay_webhook_tx(self, reference="TEST-WEBHOOK-SEC"):
        return self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": reference,
                "amount": 60.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
                "easypay_checkout_id": "checkout-wh-1",
            }
        )

    def _post_webhook(self, payload):
        return self.url_open(
            "/payment/easypay/webhook/generic",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    @staticmethod
    def _easypay_webhook_api(checkout, single, capture, authorisation=None):
        def _api(method, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            if "/checkout/" in url:
                resp.json.return_value = checkout
            elif "/capture/" in url:
                resp.json.return_value = capture
            elif "/authorisation/" in url:
                resp.json.return_value = authorisation or {}
            else:
                resp.json.return_value = single
            return resp

        return _api

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_webhook_unavailable_read_leaves_transaction_untouched(self, mock_request):
        """When the authenticated read is unavailable the transaction state
        and provider_reference stay untouched and EasyPay gets a 503."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        tx = self._easypay_webhook_tx()
        response = self._post_webhook(
            {"key": tx.reference, "type": "capture", "status": "success"}
        )
        self.assertEqual(response.status_code, 503)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")
        self.assertFalse(tx.provider_reference)
        self.assertFalse(tx.easypay_transaction_id)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_webhook_mismatched_amount_leaves_transaction_untouched(self, mock_request):
        """Authenticated data for a different amount is a permanent
        mismatch: acknowledged but never applied."""
        checkout, single, capture = self._easypay_webhook_fixtures()
        single["value"] = 999.0
        mock_request.side_effect = self._easypay_webhook_api(checkout, single, capture)
        tx = self._easypay_webhook_tx()
        response = self._post_webhook(
            {"key": tx.reference, "type": "capture", "status": "success"}
        )
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")
        self.assertFalse(tx.provider_reference)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_webhook_mismatched_payment_id_leaves_transaction_untouched(
        self, mock_request
    ):
        """A stored provider_reference conflicting with the authenticated
        payment id is rejected."""
        checkout, single, capture = self._easypay_webhook_fixtures()
        mock_request.side_effect = self._easypay_webhook_api(checkout, single, capture)
        tx = self._easypay_webhook_tx()
        tx.provider_reference = "pay-foreign"
        response = self._post_webhook(
            {"key": tx.reference, "type": "capture", "status": "success"}
        )
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "draft")
        self.assertEqual(tx.provider_reference, "pay-foreign")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_authorisation_event_does_not_supersede_submitted_capture(
        self, mock_request
    ):
        """Once a capture id is recorded, a repeated authorisation event is
        acknowledged without touching the pending transaction — even though
        the authenticated authorisation read would report success; a later
        verified capture still completes it."""
        checkout, single, capture = self._easypay_webhook_fixtures(
            reference="TEST-AUTH-ORDER"
        )
        capture["status"] = "success"
        authorisation = {
            "id": "pay-wh-1",
            "status": "success",
            "key": "TEST-AUTH-ORDER",
            "currency": "EUR",
            "value": 60.0,
        }
        mock_request.side_effect = self._easypay_webhook_api(
            checkout, single, capture, authorisation=authorisation
        )

        tx = self._easypay_webhook_tx(reference="TEST-AUTH-ORDER")
        tx.provider_reference = "pay-wh-1"
        tx.easypay_transaction_id = "cap-wh-1"
        tx._set_pending()

        response = self._post_webhook(
            {"key": tx.reference, "type": "authorisation", "status": "success"}
        )
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "pending")

        response = self._post_webhook(
            {
                "key": tx.reference,
                "type": "capture",
                "transaction": {"id": "cap-wh-1"},
            }
        )
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")

    # ── Void webhooks ─────────────────────────────────────────────────

    def _void_webhook_tx(self, void_id="void-wh-1"):
        tx = self._easypay_webhook_tx(reference="TEST-VOID-WH")
        tx.provider_reference = "pay-void-wh"
        tx.easypay_void_id = void_id
        tx._set_authorized()
        return tx

    @staticmethod
    def _void_webhook_api(void_data):
        def _api(method, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.json.return_value = void_data if "/void/" in url else {}
            return resp

        return _api

    def _post_void_webhook(self, void_id="void-wh-1"):
        return self.url_open(
            "/payment/easypay/webhook/generic",
            data=json.dumps({"type": "void", "id": void_id}),
            headers={"Content-Type": "application/json"},
        )

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_void_webhook_success_cancels_transaction(self, mock_request):
        """A verified successful void cancels the authorized transaction and
        keeps the stored void id for duplicate handling."""
        mock_request.side_effect = self._void_webhook_api(
            {"id": "void-wh-1", "status": "success"}
        )
        tx = self._void_webhook_tx()
        response = self._post_void_webhook()
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "cancel")
        self.assertEqual(tx.easypay_void_id, "void-wh-1")

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_void_webhook_pending_keeps_authorized(self, mock_request):
        """A corroborated pending/processing void changes nothing."""
        for status in ("pending", "processing"):
            mock_request.side_effect = self._void_webhook_api(
                {"id": "void-wh-1", "status": status}
            )
            tx = self._void_webhook_tx()
            response = self._post_void_webhook()
            self.assertEqual(response.status_code, 200)
            tx.invalidate_recordset()
            self.assertEqual(tx.state, "authorized")
            self.assertEqual(tx.easypay_void_id, "void-wh-1")
            tx.unlink()

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_void_webhook_failed_releases_guard(self, mock_request):
        """A verified failed void clears the stored id so staff can retry,
        while the authorisation itself stays valid."""
        mock_request.side_effect = self._void_webhook_api(
            {"id": "void-wh-1", "status": "failed"}
        )
        tx = self._void_webhook_tx()
        response = self._post_void_webhook()
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "authorized")
        self.assertFalse(tx.easypay_void_id)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_void_webhook_unresolved_read_retries(self, mock_request):
        """Missing reads, missing ids and unknown statuses ask EasyPay to
        retry with a 503; a mismatched id is acknowledged without update."""
        tx = self._void_webhook_tx()

        mock_request.side_effect = self._void_webhook_api({})
        self.assertEqual(self._post_void_webhook().status_code, 503)

        mock_request.side_effect = self._void_webhook_api({"status": "success"})
        self.assertEqual(self._post_void_webhook().status_code, 503)

        mock_request.side_effect = self._void_webhook_api(
            {"id": "void-wh-1", "status": "mysterious"}
        )
        self.assertEqual(self._post_void_webhook().status_code, 503)

        mock_request.side_effect = self._void_webhook_api(
            {"id": "void-other", "status": "success"}
        )
        self.assertEqual(self._post_void_webhook().status_code, 200)

        tx.invalidate_recordset()
        self.assertEqual(tx.state, "authorized")
        self.assertEqual(tx.easypay_void_id, "void-wh-1")

    def test_void_webhook_without_ids_is_acked(self):
        """A void event carrying no resource ids is acknowledged without
        any lookup or provider call."""
        response = self.url_open(
            "/payment/easypay/webhook/generic",
            data=json.dumps({"type": "void"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)

    @mute_logger("odoo.addons.payment_easypay_oca.controllers.webhooks")
    def test_webhook_malformed_payload_rejected(self):
        """Malformed JSON bodies are rejected with 400."""
        for body in ("not-json{{{", "[1, 2, 3]"):
            response = self.url_open(
                "/payment/easypay/webhook/generic",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(response.status_code, 400)

    @patch("odoo.addons.payment_easypay_oca.models.payment_provider.requests.request")
    def test_checkout_page_uses_server_stored_manifest(self, mock_request):
        """The checkout page renders the manifest stored server-side in the
        browser session; query-string data cannot override it and unsafe
        punctuation stays escaped."""
        session_secret = "sess-'</script><script>alert(1)</script>'"
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "checkout-page-1",
            "session": session_secret,
            "config": {"lang": "pt"},
        }
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method.id,
                "reference": "TEST-PAGE-001",
                "amount": 80.0,
                "currency_id": self.currency.id,
                "partner_id": self.partner.id,
            }
        )
        token = tx._get_processing_values()["access_token"]
        result = self.make_jsonrpc_request(
            "/payment/easypay/create_checkout_session",
            params={"reference": tx.reference, "access_token": token},
        )
        self.assertTrue(result.get("success"))

        forged = json.dumps(
            {"id": "checkout-page-1", "session": "FORGED-SESSION", "config": {}}
        )
        response = self.url_open(
            "/payment/easypay/checkout"
            f"?session_id=checkout-page-1&manifest={quote(forged)}"
        )
        self.assertEqual(response.status_code, 200)
        page_html = response.text
        self.assertIn("data-easypay=", page_html)
        self.assertIn("checkout-page-1", page_html)
        self.assertNotIn("FORGED-SESSION", page_html)
        # Punctuation in the server manifest is attribute-escaped.
        self.assertIn("&lt;/script&gt;", page_html)

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

        # A token minted for a different purpose (the generic payment
        # access token) is not accepted either.
        wrong_scope = hmac_tool(self.env(su=True), "generate_access_token", str(tx.id))
        result = self.make_jsonrpc_request(
            "/payment/easypay/create_checkout_session",
            params={"reference": tx.reference, "access_token": wrong_scope},
        )
        self.assertEqual(result.get("error"), "Invalid access token")
        self.assertFalse(tx.easypay_checkout_id)

        # Neither is a non-ASCII string (constant-time comparison requires
        # ASCII input).
        result = self.make_jsonrpc_request(
            "/payment/easypay/create_checkout_session",
            params={"reference": tx.reference, "access_token": "tökén-✓"},
        )
        self.assertEqual(result.get("error"), "Invalid access token")
        self.assertFalse(tx.easypay_checkout_id)

        # The capability carried by the real processing values — accepted
        token = tx._get_processing_values()["access_token"]
        result = self.make_jsonrpc_request(
            "/payment/easypay/create_checkout_session",
            params={"reference": tx.reference, "access_token": token},
        )
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("checkout_id"), "checkout-token-1")
        tx.invalidate_recordset()
        self.assertEqual(tx.easypay_checkout_id, "checkout-token-1")


class EasyPaySandboxSetup:
    """Opt-in live tests against the EasyPay sandbox (api.test.easypay.pt).

    These run only when explicitly selected with the ``easypay_live`` tag
    and the ``EASYPAY_TEST_ACCOUNT_ID``/``EASYPAY_TEST_API_KEY`` environment
    variables are set; the normal test run never reaches the network.
    """

    @classmethod
    def setUpClass(cls):
        account_id = os.getenv("EASYPAY_TEST_ACCOUNT_ID", "").strip()
        api_key = os.getenv("EASYPAY_TEST_API_KEY", "").strip()
        if not account_id or not api_key:
            raise SkipTest(
                "Set EASYPAY_TEST_ACCOUNT_ID and EASYPAY_TEST_API_KEY "
                "to run EasyPay sandbox tests."
            )
        super().setUpClass()
        cls.provider = cls.env["payment.provider"].create(
            {
                "name": "EasyPay Sandbox",
                "code": "easypay",
                "state": "test",
                "easypay_account_id": account_id,
                "easypay_api_key": api_key,
            }
        )

    def setUp(self):
        super().setUp()
        self.assertEqual(
            self.provider._easypay_get_api_url(),
            "https://api.test.easypay.pt",
        )


@tagged("post_install", "-at_install", "-standard", "easypay_live")
class TestEasyPaySandbox(EasyPaySandboxSetup, HttpCase):
    """Live EasyPay sandbox smoke tests over HTTP."""

    def test_sandbox_connection_succeeds(self):
        """An administrator can check connectivity with sandbox credentials."""
        result = self.provider.action_easypay_test_connection()
        self.assertTrue(
            result["params"]["type"] in ("success", "warning")
            and result["params"]["message"].startswith("Connection successful!"),
            "Odoo did not confirm the EasyPay sandbox connection",
        )

    def test_sandbox_creates_multibanco_checkout(self):
        """A customer can open an unsubmitted Multibanco checkout in the
        sandbox."""
        if os.getenv("EASYPAY_TEST_ALLOW_WRITES") != "1":
            self.skipTest(
                "Set EASYPAY_TEST_ALLOW_WRITES=1 to create a checkout "
                "in the EasyPay sandbox."
            )
        self.provider.easypay_mb_expiration_days = 7
        partner = self.env["res.partner"].create(
            {
                "name": "EasyPay Sandbox Test",
                "email": "easypay-test@example.com",
            }
        )
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.env.ref(
                    "payment.payment_method_multibanco"
                ).id,
                "reference": f"SANDBOX-{uuid4().hex}",
                "amount": 10.0,
                "currency_id": self.env.ref("base.EUR").id,
                "partner_id": partner.id,
            }
        )

        result = self.make_jsonrpc_request(
            "/payment/easypay/create_checkout_session",
            params={
                "reference": tx.reference,
                "access_token": tx._get_processing_values()["access_token"],
            },
        )
        self.assertTrue(
            isinstance(result, dict) and result.get("success") is True,
            "EasyPay checkout creation failed",
        )
        checkout_id = result.get("checkout_id")
        self.assertTrue(
            isinstance(checkout_id, str) and bool(checkout_id),
            "EasyPay checkout response has no checkout ID",
        )
        page = self.url_open(
            "/payment/easypay/checkout?session_id=" + quote(checkout_id, safe="")
        )
        self.assertEqual(page.status_code, 200)
        self.assertTrue("data-easypay=" in page.text, "The checkout page did not load")


@tagged("post_install", "-at_install", "-standard", "easypay_live")
class TestEasyPaySandboxWebhooks(EasyPaySandboxSetup, TransactionCase):
    """Live EasyPay sandbox webhook registration test."""

    def test_sandbox_configures_webhooks(self):
        """An administrator can register all three sandbox notifications."""
        base_url = os.getenv("EASYPAY_TEST_WEBHOOK_BASE_URL", "").strip().rstrip("/")
        if os.getenv("EASYPAY_TEST_ALLOW_WRITES") != "1" or not base_url:
            self.skipTest(
                "Set EASYPAY_TEST_ALLOW_WRITES=1 and EASYPAY_TEST_WEBHOOK_BASE_URL "
                "to test EasyPay sandbox webhook registration."
            )
        try:
            url = urlsplit(base_url)
            valid = (
                url.scheme == "https"
                and url.hostname
                and "." in url.hostname
                and url.hostname != "localhost"
                and not url.hostname.endswith((".localhost", ".local"))
                and url.username is None
                and (url.port is None or url.port > 0)
                and not (url.path or url.query or url.fragment)
                and base_url == f"https://{url.netloc}"
                and not any(char.isspace() for char in base_url)
            )
        except ValueError:
            valid = False
        self.assertTrue(
            bool(valid), "Set the webhook base URL to a public HTTPS origin"
        )
        self.env["ir.config_parameter"].set_param("web.base.url", base_url)
        self.assertTrue(
            self.provider.get_base_url() == base_url,
            "The test provider did not resolve to the requested webhook base URL",
        )
        before = self._read_sandbox_webhooks()
        self.assertTrue(
            all(before.values()),
            "The test needs three existing webhook URLs that can be restored",
        )
        expected = {key: f"{base_url}/payment/easypay/webhook/{key}" for key in before}
        self.assertTrue(before != expected, "Use a different URL to test registration")
        self.addCleanup(self._restore_sandbox_webhooks, before, expected)
        result = self.provider.action_easypay_configure_webhooks()
        self.assertTrue(
            result["params"]["type"] == "success",
            "Odoo could not register the sandbox webhooks; check config:update scope",
        )
        self.assertTrue(
            self._read_sandbox_webhooks() == expected,
            "EasyPay did not store all three sandbox webhook URLs",
        )

    def _read_sandbox_webhooks(self):
        expected_account = (
            os.getenv("EASYPAY_TEST_CONFIG_ACCOUNT_UUID", "").strip()
            or self.provider.easypay_account_id
        )
        config = self.provider._easypay_make_request("/2.0/config", method="GET")
        account = config.get("account") if isinstance(config, dict) else None
        self.assertTrue(
            isinstance(account, str)
            and account.strip().lower() == expected_account.lower(),
            "EasyPay returned an unexpected payment account UUID; "
            "refusing to update webhooks",
        )
        values = {
            key: config.get(key) for key in ("generic", "authorisation", "transaction")
        }
        self.assertTrue(
            all(isinstance(value, str) for value in values.values()),
            "EasyPay did not return the three sandbox webhook URLs",
        )
        return values

    def _restore_sandbox_webhooks(self, before, expected):
        current = self._read_sandbox_webhooks()
        if current == before:
            return
        self.assertTrue(
            all(current[key] in (before[key], expected[key]) for key in before),
            "Sandbox webhook settings changed externally; "
            "restore them in the backoffice",
        )
        self.provider._easypay_make_request(
            "/2.0/config", payload=before, method="PATCH"
        )
        self.assertTrue(
            self._read_sandbox_webhooks() == before,
            "Could not restore the sandbox webhook settings; check the backoffice",
        )
