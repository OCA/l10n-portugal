# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging
import time

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import hmac as hmac_tool

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    easypay_transaction_id = fields.Char(
        string="EasyPay Transaction ID",
        help="The transaction ID returned by EasyPay",
        readonly=True,
    )
    easypay_checkout_id = fields.Char(
        string="EasyPay Checkout ID",
        help="The checkout session ID returned by EasyPay",
        readonly=True,
    )
    easypay_payment_method = fields.Char(
        string="EasyPay Payment Method",
        help="The payment method selected by customer (cc, mb, mbw, etc.)",
        readonly=True,
    )
    easypay_capture_status = fields.Char(
        string="EasyPay Capture Status",
        help="The capture status (paid, pending, authorised, etc.)",
        readonly=True,
    )
    easypay_mb_entity = fields.Char(
        string="MB Entity",
        help="Multibanco entity number for the payment reference",
        readonly=True,
    )
    easypay_mb_reference = fields.Char(
        string="MB Reference",
        help="Multibanco reference number for the payment",
        readonly=True,
    )
    easypay_mb_expiration = fields.Char(
        string="MB Expiration",
        help="Expiration date/time for the Multibanco reference",
        readonly=True,
    )
    easypay_payment_details = fields.Json(
        string="EasyPay Payment Details",
        help="Full payment details from EasyPay webhook",
        readonly=True,
    )

    def _find_easypay_transaction(self, payment_id, reference):
        """Find an EasyPay transaction by reference or payment/checkout ID.

        :param str payment_id: EasyPay payment or checkout ID — used by webhooks
            and the checkout page, where only an opaque ID is available.
        :param str reference: Odoo transaction reference — used by checkout
            callbacks and session creation, where the reference is passed as ``key``.
        """
        if reference:
            return self.search(
                [("reference", "=", reference), ("provider_code", "=", "easypay")],
                limit=1,
            )
        if payment_id:
            return self.search(
                [
                    "&",
                    "|",
                    ("provider_reference", "=", payment_id),
                    ("easypay_checkout_id", "=", payment_id),
                    ("provider_code", "=", "easypay"),
                ],
                limit=1,
            )
        return self.browse()

    def _get_specific_processing_values(self, processing_values):
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code == "easypay":
            # Access token verified by the checkout-session endpoint.
            # Minted via hmac directly (same scope as
            # payment_utils.generate_access_token) because the latter
            # requires an active HTTP request, which is not guaranteed here.
            res["access_token"] = hmac_tool(
                self.env(su=True), "generate_access_token", str(self.id)
            )
        return res

    def _process_notification_data(self, notification_data):
        """Override of payment to process the notification data."""
        super()._process_notification_data(notification_data)
        if self.provider_code != "easypay":
            return

        # Extract relevant data from notification
        payment_id = notification_data.get("id")
        payment_data = notification_data.get("payment", {})
        _methods = payment_data.get("methods") or []
        payment_method = payment_data.get("method") or (
            _methods[0] if _methods else None
        )

        # _resolved_status: injected by the webhook controller after resolving
        # EasyPay's event-level "success" to a concrete payment status.
        # payment.status: from Checkout GET response (sync poll path).
        status = notification_data.get("_resolved_status") or payment_data.get("status")
        _logger.debug(
            "Processing notification for %s: status=%r (resolved=%r raw=%r) method=%s",
            self.reference,
            status,
            notification_data.get("_resolved_status"),
            payment_data.get("status"),
            payment_method,
        )

        # Update transaction with EasyPay data
        if payment_id and not self.provider_reference:
            self.provider_reference = payment_id

        # Capture transaction ID — needed for refunds and manual capture.
        # Checkout flow nests it under payment.capture.id;
        # single flow nests it under capture.id.
        capture_id = payment_data.get("capture", {}).get("id") or notification_data.get(
            "capture", {}
        ).get("id")
        if capture_id and not self.easypay_transaction_id:
            self.easypay_transaction_id = capture_id

        if payment_method:
            self.easypay_payment_method = payment_method
        if status:
            self.easypay_capture_status = status
        self.easypay_payment_details = notification_data

        # Create token for frequent (tokenized) payments.
        # The token references the EasyPay payment ID (payment.id in checkout,
        # top-level id in single flow) for future captures.
        token_ref = payment_data.get("id") or payment_id
        just_tokenized = False
        if self.tokenize and token_ref and not self.token_id:
            # The checkout GET only returns payment.method as a string
            # (e.g. "cc"); card details (last_four, card_type) are only
            # available from the single/frequent GET endpoint.
            method_data = self._easypay_fetch_method_data(token_ref)
            self._easypay_create_token(token_ref, method_data=method_data)
            just_tokenized = True

        # Transition the Odoo payment state.
        # Special case: if we just tokenized for the first time (frequent checkout),
        # immediately capture the current order using the new token, then poll the
        # capture result to confirm synchronously. Webhook remains the fallback.
        if (
            just_tokenized
            and self.amount
            and status in ("tokenized", "authorized", "authorised")
        ):
            try:
                capture_response = self._easypay_capture(token_ref)
                _logger.debug(
                    "Capture response for %s: status=%r id=%s",
                    self.reference,
                    capture_response.get("status"),
                    self.easypay_transaction_id,
                )
                self._easypay_apply_capture_result(capture_response)
            except Exception as e:
                _logger.exception(
                    "Immediate capture after tokenization failed for %s: %s",
                    self.reference,
                    e,
                )
                self._set_error(str(e))
        else:
            self._apply_payment_state(status, notification_data)

    def _apply_payment_state(self, status, notification_data):
        """Map an EasyPay status string to an Odoo state transition."""
        if status in ("pending", "waiting", "success"):
            self._set_pending()
        elif status in ("authorized", "authorised"):
            self._set_authorized()
        elif status in ("captured", "paid", "complete", "tokenized"):
            self._set_done()
        elif status in ("cancelled", "canceled"):
            self._set_canceled()
        elif status in ("failed", "error"):
            error_msg = notification_data.get("message", ["Payment failed"])
            if isinstance(error_msg, list):
                error_msg = ", ".join(str(m) for m in error_msg)
            self._set_error(error_msg)
        elif self.state == "draft":
            _logger.info(
                "Transaction %s: unrecognised status %r in draft — setting pending",
                self.reference,
                status,
            )
            self._set_pending()
        else:
            _logger.warning(
                "Transaction %s: ignoring unrecognised status %r (current: %s)",
                self.reference,
                status,
                self.state,
            )

    def _easypay_create_token(self, payment_id, method_data=None):
        """Create a payment token for frequent payments on this transaction.

        :param str payment_id: EasyPay payment.id used as provider_ref for
                               future captures via POST /2.0/capture/{id}
        :param dict method_data: Optional EasyPay method object containing
            card_type, last_four, sdd_mandate.iban, etc.
        """
        if self.token_id:
            return
        payment_details = self._easypay_token_display(payment_id, method_data)
        token = self.env["payment.token"].create(
            {
                "provider_id": self.provider_id.id,
                "partner_id": self.partner_id.id,
                "provider_ref": payment_id,
                "payment_method_id": self.payment_method_id.id,
                "payment_details": payment_details,
            }
        )
        self.token_id = token.id
        _logger.info(
            "Payment token %s created for transaction %s",
            payment_id,
            self.reference,
        )

    def _easypay_fetch_method_data(self, payment_id):
        """Fetch card/method details from the single or frequent endpoint.

        The checkout GET only returns the method code as a string.
        The single/frequent GET returns a full method object with
        last_four, card_type, sdd_mandate, etc.

        :param str payment_id: EasyPay payment ID.
        :return: method dict or empty dict.
        """
        for endpoint in (f"/2.0/frequent/{payment_id}", f"/2.0/single/{payment_id}"):
            try:
                data = self.provider_id._easypay_make_request(endpoint, method="GET")
                method = data.get("method")
                if isinstance(method, dict):
                    return method
            except Exception:
                continue
        return {}

    @staticmethod
    def _easypay_token_display(payment_id, method_data=None):
        """Build a human-readable payment_details string for a token.

        Odoo automatically prepends ``•••• `` padding in the token's
        ``_build_display_name``, so we only store the clear-text part.
        """
        if method_data and isinstance(method_data, dict):
            last_four = method_data.get("last_four")
            card_type = method_data.get("card_type", "")
            if last_four:
                return f"{card_type} {last_four}".strip()
            iban = (method_data.get("sdd_mandate") or {}).get("iban")
            if iban:
                return f"SEPA {iban[-4:]}"
        return payment_id[-4:] if len(payment_id) > 4 else payment_id

    def _send_payment_request(self):
        """Override of payment to send a token-based payment request to EasyPay."""
        if self.provider_code != "easypay":
            return super()._send_payment_request()

        if not self.token_id:
            raise ValidationError(
                _("Cannot charge: No payment token found for this transaction.")
            )
        if not self.token_id.provider_ref:
            raise ValidationError(
                _("Cannot charge: Payment token has no EasyPay reference.")
            )
        self._easypay_capture(self.token_id.provider_ref)
        # The capture is submitted; the webhook will confirm the final state.
        self._set_pending()

    def _send_refund_request(self, amount_to_refund=None):
        """Send refund request to EasyPay."""
        if self.provider_code == "easypay" and not self.easypay_transaction_id:
            raise ValidationError(_("Cannot refund: No capture transaction ID found."))

        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        if self.provider_code != "easypay":
            return refund_tx
        response = self.provider_id._easypay_make_request(
            f"/2.0/refund/{self.easypay_transaction_id}",
            {"value": -(refund_tx.amount)},
        )
        self.provider_id._easypay_raise_for_status(response, "refund")

        refund_tx.provider_reference = response.get("id")
        refund_tx._set_pending()
        return refund_tx

    def _send_capture_request(self):
        """Send capture request to EasyPay for an authorised payment."""
        if self.provider_code != "easypay":
            return super()._send_capture_request()
        if not self.provider_reference:
            raise ValidationError(
                _("Cannot capture: No EasyPay payment ID found for this transaction.")
            )
        response = self._easypay_capture(self.provider_reference)
        self._easypay_apply_capture_result(response)

    def _easypay_apply_capture_result(self, capture_response):
        """Resolve the transaction state from a POST /capture response.

        A final status settles the transaction immediately; anything else
        (including the API envelope's plain 'ok') is polled, with the webhook
        as the ultimate fallback.
        """
        capture_status = capture_response.get("status", "")
        if capture_status in ("paid", "captured"):
            self._set_done()
        elif capture_status in ("authorized", "authorised"):
            self._set_authorized()
        else:
            self._poll_capture_status()

    def _poll_capture_status(self, retries=3):
        """Poll GET /2.0/capture/{easypay_transaction_id} until a final status appears.

        Called after a tokenized capture returns a non-final status.
        Applies the resolved state directly; webhook remains the fallback.

        :param int retries: Number of attempts (back-off: 2s, 4s, 6s).
        """
        capture_id = self.easypay_transaction_id
        if not capture_id:
            _logger.warning(
                "Cannot poll capture: no easypay_transaction_id on %s", self.reference
            )
            self._set_pending()
            return

        for attempt in range(1, retries + 1):
            try:
                data = self.provider_id._easypay_make_request(
                    f"/2.0/capture/{capture_id}", method="GET"
                )
            except Exception as e:
                _logger.warning(
                    "Capture poll attempt %d for %s failed: %s",
                    attempt,
                    self.reference,
                    e,
                )
                time.sleep(attempt * 2)
                continue

            capture_status = data.get("status", "")
            _logger.debug(
                "Capture poll attempt %d for %s: status=%r",
                attempt,
                self.reference,
                capture_status,
            )
            if capture_status in ("paid", "captured"):
                self._set_done()
                return
            elif capture_status in ("authorized", "authorised"):
                self._set_authorized()
                return
            time.sleep(attempt * 2)

        _logger.warning(
            "Capture status not final after %d retries for %s — webhook will confirm.",
            retries,
            self.reference,
        )
        self._set_pending()

    def _easypay_capture(self, capture_ref):
        """POST /2.0/capture/{capture_ref}, store transaction ID, return response"""
        response = self.provider_id._easypay_make_request(
            f"/2.0/capture/{capture_ref}",
            {
                "descriptive": self.reference,
                "transaction_key": self.reference,
                "value": self.amount,
            },
        )
        self.provider_id._easypay_raise_for_status(response, "capture")
        self.easypay_transaction_id = response.get("id")
        return response

    def _send_void_request(self):
        """Send void request to EasyPay."""
        if self.provider_code != "easypay":
            return super()._send_void_request()

        if not self.provider_reference:
            raise ValidationError(
                _("Cannot void: No EasyPay payment ID found for this transaction.")
            )
        response = self.provider_id._easypay_make_request(
            f"/2.0/authorisation/{self.provider_reference}/void"
        )
        self.provider_id._easypay_raise_for_status(response, "void")
        self._set_canceled()
