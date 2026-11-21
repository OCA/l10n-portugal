# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging

import werkzeug

from odoo import http
from odoo.http import request

from odoo.addons.payment import utils as payment_utils

from . import webhooks as easypay_webhooks
from .checkout_session import find_owned_checkout_transaction

_logger = logging.getLogger(__name__)

# Authenticated payment-level statuses that count as a verified final
# state: an in-flight browser callback must never downgrade them.
_FINAL_PAYMENT_STATUSES = frozenset(
    {
        "paid",
        "captured",
        "authorized",
        "authorised",
        "cancelled",
        "canceled",
        "failed",
        "error",
    }
)


class EasyPayCheckoutCallbackController(http.Controller):
    """Handle EasyPay checkout browser callbacks (success, cancel, MB
    reference).

    Success and cancel are fired by the EasyPay SDK inside the customer's
    browser — they are not inbound EasyPay webhooks. They only identify
    which server-side checkout session they belong to; every piece of
    payment data is re-read from EasyPay with provider credentials before
    being applied.
    """

    # ── Route handlers ────────────────────────────────────────────────

    @http.route(
        "/payment/easypay/checkout/success",
        type="http",
        auth="public",
        methods=["POST"],
        save_session=False,
    )
    def easypay_checkout_success(self, **data):
        session_id = data.get("session_id")
        tx_sudo = find_owned_checkout_transaction(session_id)
        if not tx_sudo:
            _logger.debug("Checkout success callback without an owned session")
            return werkzeug.utils.redirect("/payment/status", code=303)

        verifier = easypay_webhooks.EasyPayWebhookController()
        kind, checkout = verifier._read_checkout(tx_sudo)
        if kind != easypay_webhooks._READ_OK:
            # Nothing verified — leave the transaction untouched; the
            # webhooks will resolve it.
            return werkzeug.utils.redirect("/payment/status", code=303)

        if tx_sudo.tokenize and checkout["payment_type"] == "frequent":
            # Frequent checkouts tokenize and capture through the shared
            # verifier; errors propagate so the request can be retried.
            verifier._complete_frequent_checkout(tx_sudo, checkout)
            return werkzeug.utils.redirect("/payment/status", code=303)

        kind, payment = verifier._read_single(tx_sudo, checkout["payment_id"])
        if kind != easypay_webhooks._READ_OK:
            return werkzeug.utils.redirect("/payment/status", code=303)

        kind, notification = verifier._resolve_capture_notification(
            tx_sudo, {"transaction_id": None}, verified=payment
        )
        if kind == easypay_webhooks._READ_OK:
            try:
                tx_sudo._handle_notification_data("easypay", notification)
            except Exception as e:
                _logger.exception(
                    "Error processing verified checkout data for %s: %s",
                    tx_sudo.reference,
                    e,
                )
                tx_sudo._set_error(str(e))

        mb_details = self._verified_mb_details(payment)
        if mb_details:
            # Multibanco entity/reference/expiration are stored only from
            # the authenticated EasyPay read — never from the callback.
            tx_sudo.easypay_mb_entity = mb_details["entity"]
            tx_sudo.easypay_mb_reference = mb_details["reference"]
            expiration = payment.get("expiration_time")
            tx_sudo.easypay_mb_expiration = str(expiration) if expiration else ""
            verified_status = payment.get("payment_status")
            has_final_state = (
                isinstance(verified_status, str)
                and verified_status.lower() in _FINAL_PAYMENT_STATUSES
            )
            if tx_sudo.state == "draft" and not has_final_state:
                tx_sudo._set_pending()
            if tx_sudo.state == "pending":
                access_token = payment_utils.generate_access_token(
                    "easypay_mb_reference", tx_sudo.id
                )
                return request.redirect(
                    f"/payment/easypay/mb_reference/{tx_sudo.id}"
                    f"?access_token={access_token}"
                )

        return werkzeug.utils.redirect("/payment/status", code=303)

    @http.route(
        "/payment/easypay/mb_reference/<int:tx_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        website=True,
        save_session=False,
    )
    def easypay_mb_reference(self, tx_id, access_token=None, **_kwargs):
        """Display Multibanco payment reference details."""
        if not payment_utils.check_access_token(
            access_token, "easypay_mb_reference", tx_id
        ):
            raise werkzeug.exceptions.Forbidden()
        tx_sudo = request.env["payment.transaction"].sudo().browse(tx_id).exists()
        if not tx_sudo or not tx_sudo.easypay_mb_entity:
            return request.redirect("/payment/status")
        # Format reference as "xxx xxx xxx" groups of 3 digits
        raw_ref = tx_sudo.easypay_mb_reference or ""
        digits = raw_ref.replace(" ", "")
        formatted_ref = " ".join(digits[i : i + 3] for i in range(0, len(digits), 3))
        return request.render(
            "payment_easypay_oca.mb_reference_page",
            {
                "tx": tx_sudo,
                "entity": tx_sudo.easypay_mb_entity,
                "reference": formatted_ref,
                "amount": tx_sudo.amount,
                "currency": tx_sudo.currency_id,
                "expiration": tx_sudo.easypay_mb_expiration,
                "redirect_url": tx_sudo.landing_route or "/my/home",
            },
        )

    @http.route(
        "/payment/easypay/checkout/cancel",
        type="http",
        auth="public",
        methods=["POST"],
        save_session=False,
    )
    def easypay_checkout_cancel(self, **data):
        # Browser abandonment is not an EasyPay payment cancellation.
        return werkzeug.utils.redirect("/payment/status", code=303)

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _verified_mb_details(payment):
        """Authenticated Multibanco entity/reference from the verified
        payment read; None for any other method or missing details."""
        method_details = payment.get("method_details")
        if not isinstance(method_details, dict):
            return None
        if str(method_details.get("type") or "").lower() != "mb":
            return None
        entity = method_details.get("entity")
        reference = method_details.get("reference")
        if not entity or not reference:
            return None
        return {"entity": str(entity), "reference": str(reference)}
