# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import consteq

_logger = logging.getLogger(__name__)


def find_owned_checkout_transaction(session_id):
    """Return the transaction owning this browser session's checkout.

    The callback is honoured only when ``session_id`` matches the
    checkout id stored server-side in this browser session; the lookup
    is exact on ``easypay_checkout_id`` and never falls back to payment
    ids or transaction references.
    """
    manifest = request.session.get("easypay_checkout_manifest")
    if (
        not isinstance(session_id, str)
        or not session_id
        or not isinstance(manifest, dict)
        or manifest.get("id") != session_id
    ):
        return request.env["payment.transaction"].sudo().browse()
    return (
        request.env["payment.transaction"]
        .sudo()
        .search(
            [
                ("easypay_checkout_id", "=", session_id),
                ("provider_code", "=", "easypay"),
            ],
            limit=1,
        )
    )


class EasyPayCheckoutSessionController(http.Controller):
    @http.route(
        "/payment/easypay/create_checkout_session",
        type="json",
        auth="public",
        website=True,
    )
    def create_checkout_session(self, **kwargs):
        """Create checkout session when user actually clicks Pay."""
        # Extract reference and access token from JSON-RPC params
        reference = kwargs.get("reference")
        access_token = kwargs.get("access_token")

        if not isinstance(reference, str) or not reference:
            _logger.error("Missing reference in checkout session request")
            return {"error": "Missing reference"}

        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            ._find_easypay_transaction(None, reference)
        )

        if not tx_sudo:
            _logger.error("Transaction not found: %s", reference)
            return {"error": "Transaction not found"}
        if (
            not isinstance(access_token, str)
            or not access_token.isascii()
            or not consteq(access_token, tx_sudo._easypay_checkout_access_token())
        ):
            _logger.warning(
                "Invalid access token for checkout session on tx %s", reference
            )
            return {"error": "Invalid access token"}
        tx_sudo._easypay_lock_operation()
        _logger.debug(
            "Transaction found: ref=%s state=%s checkout_id=%s",
            tx_sudo.reference,
            tx_sudo.state,
            tx_sudo.easypay_checkout_id,
        )

        checkout_id = tx_sudo.easypay_checkout_id
        if checkout_id or tx_sudo.state != "draft":
            manifest = request.session.get("easypay_checkout_manifest")
            if (
                checkout_id
                and tx_sudo.state == "draft"
                and isinstance(manifest, dict)
                and manifest.get("id") == checkout_id
            ):
                # The owning browser retried: reuse the draft checkout — its
                # payment may still settle, so a second payable session must
                # never be started for the same transaction.
                return {"checkout_id": checkout_id, "success": True}
            return {
                "error": "payment_in_progress",
                "message": (
                    "A payment is already in progress for this order. "
                    "If you requested a Multibanco reference, please use it to "
                    "complete your payment. Otherwise, please wait or refresh."
                ),
            }

        _logger.debug("Calling EasyPay POST /2.0/checkout for %s", tx_sudo.reference)
        try:
            response = tx_sudo.provider_id._easypay_create_checkout_session(tx_sudo)
        except ValidationError as e:
            _logger.exception("Checkout session creation failed: %s", e)
            return {"error": str(e)}

        checkout_id = response.get("id")
        if not checkout_id:
            _logger.error(
                "EasyPay returned no checkout ID for transaction %s", reference
            )
            return {"error": "Invalid session response: missing checkout ID"}

        tx_sudo.easypay_checkout_id = checkout_id
        # Keep the server-originated manifest in the session so the checkout
        # page never has to trust a client-supplied copy. Only the latest
        # checkout is kept per browser session.
        request.session["easypay_checkout_manifest"] = response
        _logger.debug(
            "Checkout session created: checkout_id=%s for %s",
            checkout_id,
            tx_sudo.reference,
        )

        return {
            "checkout_id": checkout_id,
            "success": True,
        }
