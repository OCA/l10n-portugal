# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging
import time

import werkzeug

from odoo import http
from odoo.http import request

from odoo.addons.payment import utils as payment_utils

_logger = logging.getLogger(__name__)


class EasyPayCheckoutCallbackController(http.Controller):
    """Handle EasyPay checkout callbacks (success, cancel, MB reference)."""

    # ── Route handlers ────────────────────────────────────────────────

    @http.route(
        "/payment/easypay/checkout/success",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        save_session=False,
    )
    def easypay_checkout_success(self, **data):
        checkout_id = data.get("id")
        reference = data.get("key")
        _logger.debug("Checkout success: id=%s ref=%s", checkout_id, reference)

        if not checkout_id and not reference:
            return werkzeug.utils.redirect("/payment/status", code=303)

        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            ._find_easypay_transaction(checkout_id, reference)
        )
        if not tx_sudo:
            _logger.debug("No transaction for id=%s ref=%s", checkout_id, reference)
            return werkzeug.utils.redirect("/payment/status", code=303)

        # ── Async payment methods ──────────────────────────────────────
        # Redirect to a method-specific page instead of the generic
        # /payment/status spinner.
        method = data.get("method", "").upper()

        # Multibanco: show entity / reference / amount.
        # NOTE: entity/reference come from the client-side SDK callback.
        # They are stored for display purposes only; the authoritative
        # payment confirmation always comes through the webhook.
        entity = data.get("entity")
        mb_reference = data.get("mb_reference")
        if method == "MB" and entity and mb_reference:
            tx_sudo.easypay_mb_entity = entity
            tx_sudo.easypay_mb_reference = mb_reference
            tx_sudo.easypay_mb_expiration = data.get("expiration", "")
            tx_sudo._set_pending()
            access_token = payment_utils.generate_access_token(tx_sudo.id)
            return request.redirect(
                f"/payment/easypay/mb_reference/{tx_sudo.id}"
                f"?access_token={access_token}"
            )

        # ── All other methods (CC, MB WAY, etc.) ─────────────────────
        # Try to confirm synchronously; fall back to pending + webhook.
        payment_data = self._poll_checkout_status(tx_sudo)
        if not payment_data:
            if tx_sudo.state not in self._TERMINAL_STATES:
                # Poll failed and no webhook resolved it — set pending as fallback.
                payment_id = data.get("payment_id")
                if tx_sudo.tokenize and payment_id:
                    method_data = tx_sudo._easypay_fetch_method_data(payment_id)
                    tx_sudo._easypay_create_token(payment_id, method_data=method_data)
                tx_sudo._set_pending()
            return werkzeug.utils.redirect("/payment/status", code=303)

        try:
            tx_sudo._process("easypay", payment_data)
        except Exception as e:
            _logger.exception(
                "Error processing polled data for %s: %s", tx_sudo.reference, e
            )
            tx_sudo._set_error(str(e))

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
        if not payment_utils.check_access_token(access_token, tx_id):
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
        methods=["GET"],
        csrf=False,
        save_session=False,
    )
    def easypay_checkout_cancel(self, **data):
        """Handle checkout cancellation from EasyPay SDK."""
        reference = data.get("key")
        session_id = data.get("session_id")
        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            ._find_easypay_transaction(session_id, reference)
        )
        if tx_sudo:
            tx_sudo._set_canceled(state_message="Payment cancelled by customer")
        return werkzeug.utils.redirect("/payment/status", code=303)

    # ── Private helpers ───────────────────────────────────────────────

    # Terminal values of payment.transaction.state (Odoo core field) that indicate
    # a webhook has already resolved the transaction — no point polling further.
    #   "done"       — payment captured/settled (funds transferred)
    #   "authorized" — funds reserved, awaiting manual capture
    #   "cancel"     — transaction cancelled
    #   "error"      — transaction failed
    # "pending" is intentionally excluded: it means async confirmation is still
    # expected (e.g. MB WAY waiting for user tap), so polling should continue.
    _TERMINAL_STATES = ("done", "authorized", "cancel", "error")

    def _poll_checkout_status(self, tx_sudo, retries=3):
        """Poll EasyPay checkout until a concrete payment status appears.

        Before each attempt the transaction is refreshed from the DB so that a
        concurrent webhook resolution is detected and polling is aborted early.

        :param tx_sudo: The transaction (sudo) to poll for.
        :param int retries: Number of polling attempts (back-off: 2s, 4s, 6s).
        :return: The checkout data dict, or None if no status was obtained.
        """
        for attempt in range(1, retries + 1):
            # Invalidate cache so we see any state written by a concurrent webhook.
            tx_sudo.invalidate_recordset()
            if tx_sudo.state in self._TERMINAL_STATES:
                _logger.debug(
                    "Poll attempt %d for %s skipped — webhook already set state=%s",
                    attempt,
                    tx_sudo.reference,
                    tx_sudo.state,
                )
                return None

            try:
                data = tx_sudo.provider_id._easypay_make_request(
                    f"/2.0/checkout/{tx_sudo.easypay_checkout_id}", method="GET"
                )
            except Exception as e:
                _logger.warning(
                    "Poll attempt %d for %s failed: %s",
                    attempt,
                    tx_sudo.reference,
                    e,
                )
                time.sleep(attempt * 2)
                continue
            _logger.debug(
                "Poll attempt %d for %s: data=%s",
                attempt,
                tx_sudo.reference,
                data,
            )
            if data.get("payment", {}).get("status"):
                return data
            # Status not yet available — wait before retrying.
            time.sleep(attempt * 2)
        _logger.warning(
            "No payment status after %d retries for %s — webhook will confirm.",
            retries,
            tx_sudo.reference,
        )
        return None
