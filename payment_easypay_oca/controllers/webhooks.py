# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging
import math
import re

from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

# Authenticated EasyPay statuses mapped to the vocabulary consumed by
# payment.transaction._apply_payment_state.
_CAPTURE_STATUS_MAP = {
    "success": "paid",
    "paid": "paid",
    "captured": "captured",
    "pending": "pending",
    "waiting": "waiting",
    "delayed": "pending",
    "failed": "failed",
}
_AUTHORISATION_STATUS_MAP = {
    "success": "authorised",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "deleted": "cancelled",
    "failed": "failed",
    "pending": "pending",
    "waiting": "pending",
}
_REFUND_STATUS_MAP = {
    "success": "done",
    "pending": "pending",
    "waiting": "pending",
    "failed": "error",
}

# Payment-level statuses accepted as settlement evidence. Anything else —
# including envelope values like 'success'/'ok' and 'complete' — is
# inconclusive and never applied.
_PAYMENT_STATUS_ALIASES = {
    "canceled": "cancelled",
    "deleted": "cancelled",
    "voided": "cancelled",
}
_KNOWN_PAYMENT_STATUSES = {
    "paid",
    "captured",
    "authorized",
    "authorised",
    "pending",
    "waiting",
    "failed",
    "error",
    "cancelled",
}

_CAPTURE_EVENT_TYPES = {"capture", "subscription_capture"}

# Result kinds returned by the authenticated-read helpers.
_READ_OK = "ok"
_READ_RETRY = "retry"
_READ_CONFLICT = "conflict"

# EasyPay identifiers are UUIDs; anything else is rejected before being
# interpolated into a request path.
_SAFE_ID_PATTERN = re.compile(r"\A[A-Za-z0-9_-]+\Z")


class EasyPayWebhookController(http.Controller):
    """Handle EasyPay webhook notifications.

    Payloads are unauthenticated hints used only to locate the transaction
    and pick which EasyPay resource to read back with provider credentials.
    State is applied exclusively from that authenticated data.
    """

    @http.route(
        "/payment/easypay/webhook/generic",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def _generic_webhook(self, **_kwargs):
        """Flat payload: {id, key, type, status, messages, date}."""
        return self._handle_webhook()

    @http.route(
        "/payment/easypay/webhook/authorisation",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def _authorisation_webhook(self, **_kwargs):
        """Dedicated authorisation payload shape."""
        return self._handle_webhook("authorisation")

    @http.route(
        "/payment/easypay/webhook/transaction",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def easypay_transaction_webhook(self, **_kwargs):
        """Nested payload carrying capture details under 'transaction'."""
        return self._handle_webhook()

    # ── Dispatch ──────────────────────────────────────────────────────

    def _handle_webhook(self, event_type_hint=None):
        try:
            data = request.get_json_data()
        except ValueError:
            _logger.warning("EasyPay webhook: malformed JSON body")
            return request.make_json_response(
                {"error": "malformed payload"}, status=400
            )
        if not isinstance(data, dict):
            _logger.warning("EasyPay webhook: non-object JSON body")
            return request.make_json_response(
                {"error": "malformed payload"}, status=400
            )

        event = self._extract_event(data, event_type_hint)
        if event["type"] == "void":
            # Void events are bound by the locally stored void id, not by
            # the generic transaction lookup.
            return self._process_void_event(event)
        tx_sudo = self._find_event_transaction(event)
        if not tx_sudo:
            _logger.debug("EasyPay webhook matched no transaction: %r", event)
            return self._easypay_webhook_unmatched(data)

        event_type = event["type"]
        if event_type == "refund":
            return self._process_refund_event(tx_sudo, event)
        if event_type == "authorisation":
            return self._process_authorisation_event(tx_sudo, event)
        return self._process_payment_event(tx_sudo, event)

    @staticmethod
    def _extract_event(data, type_hint):
        """Normalise flat and nested payloads into identifier hints only."""
        tx_data = data.get("transaction")
        tx_data = tx_data if isinstance(tx_data, dict) else {}
        auth_data = data.get("authorisation")
        auth_data = auth_data if isinstance(auth_data, dict) else {}

        def _strings(*values):
            return [v for v in values if isinstance(v, str) and v]

        event_type = next(
            (
                t
                for t in (data.get("type"), tx_data.get("type"), type_hint)
                if isinstance(t, str) and t
            ),
            None,
        )
        transaction_id = tx_data.get("id")
        return {
            "type": event_type,
            "keys": _strings(data.get("key"), tx_data.get("key")),
            "ids": _strings(data.get("id"), transaction_id, auth_data.get("id")),
            "transaction_id": transaction_id
            if isinstance(transaction_id, str)
            else None,
        }

    def _find_event_transaction(self, event):
        """Locate the transaction by merchant key first, then resource ids."""
        tx_model = request.env["payment.transaction"].sudo()
        for key in event["keys"]:
            tx = tx_model._find_easypay_transaction(None, key)
            if tx:
                return tx
        for resource_id in event["ids"]:
            tx = tx_model._find_easypay_transaction(resource_id, None)
            if tx:
                return tx
        return tx_model.browse()

    def _easypay_webhook_unmatched(self, data):
        """Extension point for modules tracking EasyPay payments outside
        ``payment.transaction`` (e.g. direct debit collections)."""
        return request.make_json_response({}, status=200)

    # ── Event processors ──────────────────────────────────────────────

    def _process_payment_event(self, tx_sudo, event):
        has_capture_ref = bool(
            tx_sudo.easypay_transaction_id or event["transaction_id"]
        )
        if event["type"] in _CAPTURE_EVENT_TYPES or has_capture_ref:
            kind, notification = self._resolve_capture_notification(tx_sudo, event)
            if kind == _READ_OK:
                return self._apply_verified_notification(tx_sudo, notification)
            if kind == _READ_CONFLICT:
                return request.make_json_response({}, status=200)
            if has_capture_ref:
                # A known capture must be resolved through the capture
                # resource — never through the payment-level fallback.
                return request.make_json_response({}, status=503)
        kind, notification = self._resolve_payment_notification(tx_sudo)
        if kind == _READ_OK:
            return self._apply_verified_notification(tx_sudo, notification)
        if kind == _READ_CONFLICT:
            return request.make_json_response({}, status=200)
        return request.make_json_response({}, status=503)

    def _process_authorisation_event(self, tx_sudo, event):
        # A submitted capture owns the outcome: a late authorisation event
        # must never supersede it.
        if tx_sudo.easypay_transaction_id:
            return request.make_json_response({}, status=200)
        kind, verified = self._payment_resource(tx_sudo)
        if kind == _READ_CONFLICT:
            return request.make_json_response({}, status=200)
        if kind != _READ_OK:
            return request.make_json_response({}, status=503)

        kind, payload = self._read_authorisation(tx_sudo, verified["payment_id"])
        if kind == _READ_RETRY:
            return request.make_json_response({}, status=503)
        if kind == _READ_CONFLICT:
            return request.make_json_response({}, status=200)
        auth = payload["data"]

        # Value/currency corroborated when present; mandatory binding
        # evidence unless the checkout read already bound them.
        currency = auth.get("currency")
        amounts_equal = self._amounts_equal(tx_sudo, auth.get("value"), tx_sudo.amount)
        if currency is not None and currency != tx_sudo.currency_id.name:
            return request.make_json_response({}, status=200)
        if amounts_equal is False:
            return request.make_json_response({}, status=200)
        if not tx_sudo.easypay_checkout_id and (
            currency is None or amounts_equal is None
        ):
            return request.make_json_response({}, status=503)

        status = _AUTHORISATION_STATUS_MAP.get(auth.get("status"))
        if status is None:
            _logger.info(
                "EasyPay authorisation webhook: unrecognised status %r for %s",
                auth.get("status"),
                tx_sudo.reference,
            )
            return request.make_json_response({}, status=503)

        verified = {"payment_id": verified["payment_id"]}
        method = auth.get("method")
        if isinstance(method, dict) and isinstance(method.get("type"), str):
            verified["method"] = method["type"].lower()
        return self._apply_verified_notification(
            tx_sudo, self._build_notification(verified, status)
        )

    def _process_void_event(self, event):
        """Resolve a locally originated void through its stored void id.

        The event only hints at which void ids EasyPay is reporting; the
        outcome is always read back from ``GET /2.0/void/{stored id}``.
        """
        if not event["ids"]:
            return request.make_json_response({}, status=200)
        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            .search(
                [
                    ("provider_code", "=", "easypay"),
                    ("easypay_void_id", "in", event["ids"]),
                ],
                limit=2,
            )
        )
        if len(tx_sudo) != 1:
            # No match, or an ambiguous one — acknowledge without touching
            # any transaction.
            _logger.info(
                "EasyPay void webhook matched %d transactions for ids %r",
                len(tx_sudo),
                event["ids"],
            )
            return request.make_json_response({}, status=200)

        void_id = tx_sudo.easypay_void_id
        data = self._easypay_get(tx_sudo.provider_id, "void", void_id)
        result = tx_sudo._easypay_apply_void_status(data)
        # "retry" covers a missing read or an unknown status — EasyPay
        # redelivers; "ok" and "conflict" are acknowledged without
        # further state changes pending redelivery.
        return request.make_json_response(
            {}, status=503 if result == _READ_RETRY else 200
        )

    def _process_refund_event(self, tx_sudo, event):
        source_tx = (
            tx_sudo.source_transaction_id if tx_sudo.operation == "refund" else tx_sudo
        )
        if not source_tx:
            return request.make_json_response({}, status=200)

        # The event must identify the local refund transaction exactly: the
        # EasyPay refund id stored as provider_reference on the child tx.
        refund_tx = source_tx.child_transaction_ids.filtered(
            lambda tx: tx.operation == "refund"
            and tx.provider_reference
            and tx.provider_reference in event["ids"]
        )[:1]
        if not refund_tx:
            _logger.info(
                "EasyPay refund webhook matched no local refund for %s",
                source_tx.reference,
            )
            return request.make_json_response({}, status=200)
        refund_id = refund_tx.provider_reference

        kind, payload = self._read_refund(source_tx, refund_id)
        if kind == _READ_RETRY:
            return request.make_json_response({}, status=503)
        if kind == _READ_CONFLICT:
            return request.make_json_response({}, status=200)
        data = payload["data"]

        # Refund amounts are compared by magnitude: the remote amount is
        # documented positive while the local amount may be signed.
        amounts_equal = self._amounts_equal(
            source_tx, data.get("value"), abs(float(refund_tx.amount))
        )
        if amounts_equal is False:
            _logger.warning(
                "EasyPay refund %s value mismatch for %s",
                refund_id,
                source_tx.reference,
            )
            return request.make_json_response({}, status=200)
        if amounts_equal is None:
            return request.make_json_response({}, status=503)

        # The refunded capture must be the one stored on the source tx.
        capture = data.get("capture")
        capture = capture if isinstance(capture, dict) else {}
        capture_id = capture.get("id")
        if not source_tx.easypay_transaction_id or not capture_id:
            return request.make_json_response({}, status=503)
        if capture_id != source_tx.easypay_transaction_id:
            _logger.warning(
                "EasyPay refund %s capture id mismatch for %s",
                refund_id,
                source_tx.reference,
            )
            return request.make_json_response({}, status=200)

        status = _REFUND_STATUS_MAP.get(data.get("status"))
        if status is None:
            return request.make_json_response({}, status=503)
        if status == "done":
            refund_tx._set_done()
        elif status == "error":
            refund_tx._set_error(_("EasyPay refund failed."))
        return request.make_json_response({}, status=200)

    # ── Verified resolution ───────────────────────────────────────────

    def _resolve_capture_notification(self, tx_sudo, event, *, verified=None):
        stored = tx_sudo.easypay_transaction_id
        supplied = event["transaction_id"]
        if stored and supplied and stored != supplied:
            return _READ_CONFLICT, None
        capture_id = stored or supplied
        if capture_id:
            return self._resolve_known_capture(tx_sudo, capture_id)

        # No specific capture id: select exactly one capture from the
        # payment resource, else fall back to its payment-level status.
        # Callers that already hold an authenticated payment read (e.g.
        # the checkout callback) pass it as ``verified`` to skip the
        # redundant resource lookup.
        if verified is None:
            kind, verified = self._payment_resource(tx_sudo)
            if kind != _READ_OK:
                return kind, None
        if "captures" not in verified:
            # A checkout binding carries no capture list — read the payment
            # resource for captures and the richer payment status.
            kind, single = self._read_single(tx_sudo, verified["payment_id"])
            if kind == _READ_CONFLICT:
                return _READ_CONFLICT, None
            if kind == _READ_OK:
                verified = single
        candidates = [
            capture
            for capture in verified.get("captures") or []
            if isinstance(capture, dict)
            and capture.get("transaction_key") == tx_sudo.reference
            and (not supplied or capture.get("id") == supplied)
        ]
        if len(candidates) == 1:
            selected_id = candidates[0].get("id")
            if not selected_id:
                return _READ_RETRY, None
            kind, cap = self._read_capture(tx_sudo, selected_id)
            if kind == _READ_CONFLICT:
                return _READ_CONFLICT, None
            if kind != _READ_OK:
                return _READ_RETRY, None
            if cap["payment_id"] != verified["payment_id"]:
                return _READ_CONFLICT, None
            status = _CAPTURE_STATUS_MAP.get(cap["status"])
            if status is None:
                return _READ_RETRY, None
            return _READ_OK, self._build_notification(
                verified, status, capture_id=selected_id
            )
        if len(candidates) > 1:
            _logger.warning(
                "EasyPay webhook: %d captures match %s — cannot select one",
                len(candidates),
                tx_sudo.reference,
            )
            return _READ_RETRY, None

        status = self._normalise_payment_status(verified.get("payment_status"))
        if status:
            return _READ_OK, self._build_notification(verified, status)
        return _READ_RETRY, None

    def _resolve_known_capture(self, tx_sudo, capture_id):
        """Resolve a notification for a specific stored or event-supplied
        capture id through the authenticated capture resource."""
        kind, cap = self._read_capture(tx_sudo, capture_id)
        if kind != _READ_OK:
            return kind, None
        kind, verified = self._bind_payment(tx_sudo, cap["payment_id"])
        if kind != _READ_OK:
            return kind, None
        status = _CAPTURE_STATUS_MAP.get(cap["status"])
        if status is None:
            return _READ_RETRY, None
        return _READ_OK, self._build_notification(
            verified, status, capture_id=capture_id
        )

    def _resolve_payment_notification(self, tx_sudo):
        kind, verified = self._payment_resource(tx_sudo)
        if kind != _READ_OK:
            return kind, None
        status = self._normalise_payment_status(verified.get("payment_status"))
        if not status:
            return _READ_RETRY, None
        return _READ_OK, self._build_notification(verified, status)

    # ── Authenticated reads ───────────────────────────────────────────

    def _easypay_get(self, provider, resource, resource_id):
        """Authenticated GET /2.0/{resource}/{id}; {} on transport failure."""
        if not isinstance(resource_id, str) or not _SAFE_ID_PATTERN.fullmatch(
            resource_id
        ):
            _logger.warning(
                "Refusing EasyPay GET %s with unsafe id %r", resource, resource_id
            )
            return {}
        try:
            data = provider._easypay_make_request(
                f"/2.0/{resource}/{resource_id}", method="GET"
            )
        except ValidationError as e:
            _logger.warning("EasyPay GET %s/%s failed: %s", resource, resource_id, e)
            return {}
        return data if isinstance(data, dict) else {}

    def _payment_resource(self, tx_sudo):
        """Authenticated payment-level read: stored checkout first, else the
        locally known payment id."""
        if tx_sudo.easypay_checkout_id:
            return self._read_checkout(tx_sudo)
        payment_id = self._stored_payment_id(tx_sudo)
        if not payment_id:
            return _READ_RETRY, None
        return self._read_single(tx_sudo, payment_id)

    def _bind_payment(self, tx_sudo, capture_payment_id=None):
        """Bind the payment behind a capture: the capture's own payment id is
        only ever compared, never used as a lookup source."""
        kind, verified = self._payment_resource(tx_sudo)
        if kind != _READ_OK:
            return kind, None
        if capture_payment_id and capture_payment_id != verified["payment_id"]:
            return _READ_CONFLICT, None
        return _READ_OK, verified

    def _read_checkout(self, tx_sudo):
        """GET /2.0/checkout/{stored id} bound by id, currency and value."""
        checkout_id = tx_sudo.easypay_checkout_id
        data = self._easypay_get(tx_sudo.provider_id, "checkout", checkout_id)
        if not data:
            return _READ_RETRY, None
        checkout = data.get("checkout")
        checkout = checkout if isinstance(checkout, dict) else {}
        payment = data.get("payment")
        payment = payment if isinstance(payment, dict) else {}

        resp_checkout_id = checkout.get("id")
        if resp_checkout_id is None:
            return _READ_RETRY, None
        if resp_checkout_id != checkout_id:
            return _READ_CONFLICT, None

        payment_id = payment.get("id")
        currency = payment.get("currency")
        value = data.get("value")
        if not payment_id or not currency or value is None:
            return _READ_RETRY, None
        if currency != tx_sudo.currency_id.name:
            return _READ_CONFLICT, None
        amounts_equal = self._amounts_equal(tx_sudo, value, tx_sudo.amount)
        if amounts_equal is False:
            return _READ_CONFLICT, None
        if amounts_equal is None:
            return _READ_RETRY, None
        # A provider_reference equal to the checkout id is legacy bad data —
        # it does not conflict and is replaced once verified.
        stored_ref = tx_sudo.provider_reference
        if stored_ref and stored_ref != checkout_id and stored_ref != payment_id:
            return _READ_CONFLICT, None

        methods = payment.get("methods")
        return _READ_OK, {
            "payment_id": payment_id,
            "payment_status": payment.get("status"),
            "payment_type": payment.get("type"),
            "checkout_status": checkout.get("status"),
            "methods": [method.lower() for method in methods if isinstance(method, str)]
            if isinstance(methods, list)
            else None,
        }

    def _read_single(self, tx_sudo, payment_id):
        """GET /2.0/single/{id} (frequent fallback) bound by id, currency,
        and value for single payments."""
        data = self._easypay_get(tx_sudo.provider_id, "single", payment_id)
        resource = "single"
        if not data:
            data = self._easypay_get(tx_sudo.provider_id, "frequent", payment_id)
            resource = "frequent"
        if not data:
            return _READ_RETRY, None

        resp_id = data.get("id")
        if resp_id is None:
            return _READ_RETRY, None
        if resp_id != payment_id:
            return _READ_CONFLICT, None
        currency = data.get("currency")
        if currency is None:
            return _READ_RETRY, None
        if currency != tx_sudo.currency_id.name:
            return _READ_CONFLICT, None

        verified = {
            "payment_id": payment_id,
            "payment_status": data.get("payment_status"),
            "captures": data.get("captures")
            if isinstance(data.get("captures"), list)
            else [],
        }
        method = data.get("method")
        method_details = method if isinstance(method, dict) else None
        verified["method_details"] = method_details
        multibanco = data.get("multibanco")
        expiration_time = (
            multibanco.get("expiration_time") if isinstance(multibanco, dict) else None
        )
        if expiration_time is None and method_details:
            # Frequent payments carry the method expiration on the method
            # object itself.
            expiration_time = method_details.get("expiration_date")
        verified["expiration_time"] = expiration_time
        if method_details and isinstance(method_details.get("type"), str):
            verified["method"] = method_details["type"].lower()

        if resource == "single":
            amounts_equal = self._amounts_equal(
                tx_sudo, data.get("value"), tx_sudo.amount
            )
            if amounts_equal is False:
                return _READ_CONFLICT, None
            if amounts_equal is None:
                return _READ_RETRY, None
        return _READ_OK, verified

    def _read_capture(self, tx_sudo, capture_id):
        """GET /2.0/capture/{id} bound by id, transaction_key and value."""
        data = self._easypay_get(tx_sudo.provider_id, "capture", capture_id)
        if not data:
            return _READ_RETRY, None

        resp_id = data.get("id")
        if resp_id is None:
            return _READ_RETRY, None
        if resp_id != capture_id:
            return _READ_CONFLICT, None
        transaction_key = data.get("transaction_key")
        if transaction_key is None:
            return _READ_RETRY, None
        if transaction_key != tx_sudo.reference:
            return _READ_CONFLICT, None
        if not data.get("payment_id"):
            return _READ_RETRY, None
        amounts_equal = self._amounts_equal(tx_sudo, data.get("value"), tx_sudo.amount)
        if amounts_equal is False:
            return _READ_CONFLICT, None
        if amounts_equal is None:
            return _READ_RETRY, None

        return _READ_OK, {
            "status": data.get("status"),
            "payment_id": data["payment_id"],
        }

    def _read_authorisation(self, tx_sudo, payment_id):
        """GET /2.0/authorisation/{payment_id} for authorisation/void events."""
        data = self._easypay_get(tx_sudo.provider_id, "authorisation", payment_id)
        if not data:
            return _READ_RETRY, None
        if not data.get("id"):
            return _READ_RETRY, None
        key = data.get("key")
        if key is not None and key != tx_sudo.reference:
            return _READ_CONFLICT, None
        return _READ_OK, {"data": data}

    def _read_refund(self, tx_sudo, refund_id):
        """GET /2.0/refund/{refund_id} bound by returned id."""
        data = self._easypay_get(tx_sudo.provider_id, "refund", refund_id)
        if not data:
            return _READ_RETRY, None
        resp_id = data.get("id")
        if resp_id is None:
            return _READ_RETRY, None
        if resp_id != refund_id:
            return _READ_CONFLICT, None
        return _READ_OK, {"data": data}

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _stored_payment_id(tx_sudo):
        """Payment id from local trusted data only — never caller-supplied.
        A provider_reference equal to the checkout id is legacy bad data,
        not a payment id."""
        ref = tx_sudo.provider_reference
        if ref and ref != tx_sudo.easypay_checkout_id:
            return ref
        if tx_sudo.token_id and tx_sudo.token_id.provider_ref:
            return tx_sudo.token_id.provider_ref
        return None

    @staticmethod
    def _amounts_equal(tx_sudo, amount1, amount2):
        """Compare amounts in the transaction currency; None when either is
        missing, non-numeric or non-finite."""
        if amount1 is None or amount2 is None:
            return None
        try:
            a1, a2 = float(amount1), float(amount2)
        except (TypeError, ValueError):
            return None
        if not (math.isfinite(a1) and math.isfinite(a2)):
            return None
        return tx_sudo.currency_id.compare_amounts(a1, a2) == 0

    @staticmethod
    def _normalise_payment_status(status):
        """Normalise an authenticated payment-level status against the
        explicit allowlist; None for anything else."""
        if not isinstance(status, str) or not status:
            return None
        status = _PAYMENT_STATUS_ALIASES.get(status.lower(), status.lower())
        return status if status in _KNOWN_PAYMENT_STATUSES else None

    @staticmethod
    def _build_notification(verified, status, capture_id=None):
        """Notification payload for _handle_notification_data in the shape
        _process_notification_data already understands."""
        payment_id = verified["payment_id"]
        payment = {"id": payment_id, "status": status}
        if verified.get("method"):
            payment["method"] = verified["method"]
        elif verified.get("methods"):
            payment["methods"] = verified["methods"]
        if capture_id:
            payment["capture"] = {"id": capture_id}
        notification = {
            "id": payment_id,
            "payment": payment,
            "_resolved_status": status,
        }
        if capture_id:
            notification["capture"] = {"id": capture_id}
        return notification

    def _apply_verified_notification(self, tx_sudo, notification_data):
        """Apply verified data; unexpected errors propagate so the request
        rolls back and EasyPay retries."""
        tx_sudo._handle_notification_data("easypay", notification_data)
        return request.make_json_response({}, status=200)
