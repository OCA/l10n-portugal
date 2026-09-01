# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class EasyPayWebhookController(http.Controller):
    """Controller to handle EasyPay webhook notifications."""

    @http.route(
        "/payment/easypay/webhook/generic",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def _generic_webhook(self, **_kwargs):
        """Handle generic event webhook from EasyPay.

        Flat payload: {id, key, type, status, messages, date}
        'type' describes the event (capture, authorisation, etc.).
        'status: success' means the event completed successfully.
        """
        data = request.get_json_data()
        event_type = data.get("type")
        status = data.get("status")
        # Map event-specific 'success' to the correct payment status
        if status == "success" and event_type in ("capture", "transaction"):
            resolved_status = "paid"
        elif status == "success" and event_type == "authorisation":
            resolved_status = "authorised"
        else:
            resolved_status = status
        return self._handle_flat_webhook(data, resolved_status)

    @http.route(
        "/payment/easypay/webhook/authorisation",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def _authorisation_webhook(self, **_kwargs):
        """Handle authorisation webhook from EasyPay.

        Same flat payload shape as generic; 'success' means authorised.
        """
        data = request.get_json_data()
        resolved_status = (
            "authorised" if data.get("status") == "success" else data.get("status")
        )
        return self._handle_flat_webhook(data, resolved_status)

    @http.route(
        "/payment/easypay/webhook/transaction",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def easypay_transaction_webhook(self, **_kwargs):
        """Handle transaction (capture detail) webhook from EasyPay.

        Nested payload: top-level id/key may be empty;
        reference and event type live inside the 'transaction' object.
        """
        data = request.get_json_data()
        tx_data = data.get("transaction", {})
        payment_id = data.get("id") or tx_data.get("id")
        reference = tx_data.get("key")
        event_type = tx_data.get("type")
        _logger.debug(
            "Transaction webhook: event=%s id=%s ref=%s",
            event_type,
            payment_id,
            reference,
        )

        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            ._find_easypay_transaction(payment_id, reference)
        )
        if not tx_sudo:
            _logger.debug(
                "No transaction for id=%s ref=%s — ignoring",
                payment_id,
                reference,
            )
            return request.make_json_response({}, status=200)

        if payment_id and not tx_sudo.provider_reference:
            tx_sudo.provider_reference = payment_id

        if event_type == "capture":
            payment_data = self._fetch_payment_data(tx_sudo)
            payment_data["_resolved_status"] = "paid"
            tx_sudo._process("easypay", payment_data)
        elif event_type == "void":
            payment_data = self._fetch_payment_data(tx_sudo)
            payment_data["_resolved_status"] = "cancelled"
            tx_sudo._process("easypay", payment_data)
        elif event_type == "refund":
            self._handle_refund_webhook(tx_sudo, tx_data)
        else:
            _logger.info(
                "Transaction webhook: unhandled event type %r for %s — ignoring",
                event_type,
                reference,
            )
        return request.make_json_response({}, status=200)

    # ── Private helpers ───────────────────────────────────────────────

    def _handle_flat_webhook(self, data, resolved_status):
        """Common handler for flat-payload webhooks (generic + authorisation)."""
        payment_id = data.get("id")
        reference = data.get("key")
        _logger.debug(
            "Flat webhook: id=%s ref=%s resolved=%s",
            payment_id,
            reference,
            resolved_status,
        )
        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            ._find_easypay_transaction(payment_id, reference)
        )
        if not tx_sudo:
            return request.make_json_response({}, status=200)
        if payment_id and not tx_sudo.provider_reference:
            tx_sudo.provider_reference = payment_id
        payment_data = self._fetch_payment_data(tx_sudo)
        payment_data["_resolved_status"] = resolved_status
        tx_sudo._process("easypay", payment_data)
        return request.make_json_response({}, status=200)

    def _handle_refund_webhook(self, source_tx, tx_data):
        """Confirm or fail a pending refund transaction from a webhook event.

        :param source_tx: The original (source) payment transaction.
        :param dict tx_data: The 'transaction' object from the webhook payload.
        """
        refund_id = tx_data.get("id")
        status = tx_data.get("status")
        # Find the refund child tx created by _send_refund_request.
        refund_tx = source_tx.child_transaction_ids.filtered(
            lambda tx: tx.operation == "refund" and tx.provider_reference == refund_id
        )
        if not refund_tx:
            _logger.warning(
                "Refund webhook: no pending refund tx with provider_reference=%s "
                "for source %s — ignoring",
                refund_id,
                source_tx.reference,
            )
            return
        if status in ("success", "ok"):
            refund_tx._set_done()
        else:
            refund_tx._set_error(f"EasyPay refund failed with status: {status}")

    def _fetch_payment_data(self, tx_sudo):
        """Fetch the full payment/checkout data from EasyPay, or return {}."""
        if tx_sudo.easypay_checkout_id:
            endpoint = f"/2.0/checkout/{tx_sudo.easypay_checkout_id}"
        elif tx_sudo.provider_reference:
            endpoint = f"/2.0/single/{tx_sudo.provider_reference}"
        else:
            return {}
        try:
            return tx_sudo.provider_id._easypay_make_request(endpoint, method="GET")
        except Exception as e:
            _logger.exception("Error fetching payment data: %s", e)
            return {}
