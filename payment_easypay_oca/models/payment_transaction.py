# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging
import math
import time
from uuid import NAMESPACE_URL, uuid5

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import hmac as hmac_tool

from .. import const

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
    easypay_void_id = fields.Char(
        string="EasyPay Void ID",
        help="The void operation ID returned by EasyPay",
        readonly=True,
        copy=False,
        index=True,
    )
    easypay_void_attempt = fields.Integer(
        string="EasyPay Void Attempt",
        help="Verified failed void attempts; keys the next void request",
        readonly=True,
        copy=False,
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
            # Checkout-session capability verified by the
            # create-checkout-session endpoint; minted via hmac directly
            # because payment_utils.generate_access_token requires an
            # active HTTP request, which is not guaranteed here.
            res["access_token"] = self._easypay_checkout_access_token()
        return res

    def _easypay_checkout_access_token(self):
        self.ensure_one()
        return hmac_tool(self.env(su=True), "easypay_checkout_session", str(self.id))

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

        # Update transaction with EasyPay data. A provider_reference equal
        # to the checkout id is legacy bad data: the verified payment id may
        # replace it (all binding checks already passed upstream).
        if payment_id and (
            not self.provider_reference
            or self.provider_reference == self.easypay_checkout_id
        ):
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
        # _verified_token_method is a private hand-off for token creation —
        # never persist the raw method details in the audit payload.
        self.easypay_payment_details = {
            key: value
            for key, value in notification_data.items()
            if key != "_verified_token_method"
        }

        # Create token for frequent (tokenized) payments.
        # The token references the EasyPay payment ID (payment.id in checkout,
        # top-level id in single flow) for future captures.
        token_ref = payment_data.get("id") or payment_id
        just_tokenized = False
        if self.tokenize and token_ref and not self.token_id:
            # The checkout GET only returns payment.method as a string
            # (e.g. "cc"); card details (last_four, card_type) are only
            # available from the single/frequent GET endpoint — or from the
            # verified method the webhook already read for this payment.
            method_data = notification_data.get(
                "_verified_token_method"
            ) or self._easypay_fetch_method_data(token_ref)
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
            # Serialize the token write before the external capture. A
            # concurrent Odoo request will retry on a conflicting
            # transaction update.
            self.flush_recordset(["token_id"])
            capture_key = (
                str(
                    uuid5(
                        NAMESPACE_URL,
                        "easypay:initial-capture:"
                        f"{self.easypay_checkout_id}:{token_ref}",
                    )
                )
                if self.easypay_checkout_id
                else None
            )
            try:
                capture_response = self._easypay_capture(
                    token_ref, idempotency_key=capture_key
                )
                _logger.debug(
                    "Capture response for %s: status=%r id=%s",
                    self.reference,
                    capture_response.get("status"),
                    self.easypay_transaction_id,
                )
                self._easypay_apply_capture_result(capture_response)
            except const.EasyPayTransportError:
                # Uncertain submission: propagate so the surrounding
                # savepoint/request rolls back and the same idempotency
                # key can be retried.
                raise
            except ValidationError as e:
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
        self._easypay_lock_operation()
        if self.easypay_transaction_id or self.state != "authorized":
            return
        if self.easypay_void_id:
            raise ValidationError(
                _(
                    "Cannot capture: a void request is pending confirmation "
                    "for this transaction."
                )
            )
        if not self.provider_reference:
            raise ValidationError(
                _("Cannot capture: No EasyPay payment ID found for this transaction.")
            )
        response = self._easypay_capture(
            self.provider_reference,
            idempotency_key=self._easypay_operation_key("capture"),
        )
        self._easypay_apply_capture_result(response)

    def _easypay_apply_capture_result(self, capture_response):
        """Resolve the transaction state from a POST /capture response.

        The POST only acknowledges the request with an 'ok' envelope — the
        capture state itself must be read back from the API, so the result
        is always resolved through ``_poll_capture_status``.
        """
        _logger.debug(
            "Capture request acknowledged for %s (capture id=%s); polling status",
            self.reference,
            capture_response.get("id"),
        )
        self._poll_capture_status()

    def _poll_capture_status(self, retries=3):
        """Poll GET /2.0/capture/{easypay_transaction_id} until a final status appears.

        Called after a capture is submitted. Applies the resolved state
        directly; the webhook remains the fallback for unresolved states.
        Authorisation is never treated as capture success: an authorised
        transaction that stays unresolved is moved to pending so it is not
        offered for capture again.

        :param int retries: Number of attempts (back-off: 2s, 4s, 6s).
        """
        capture_id = self.easypay_transaction_id
        if not capture_id:
            _logger.warning(
                "Cannot poll capture: no easypay_transaction_id on %s", self.reference
            )
            self._set_pending(extra_allowed_states=("authorized",))
            return

        for attempt in range(1, retries + 1):
            try:
                data = self.provider_id._easypay_make_request(
                    f"/2.0/capture/{capture_id}", method="GET"
                )
            except ValidationError as e:
                _logger.warning(
                    "Capture poll attempt %d for %s failed: %s",
                    attempt,
                    self.reference,
                    e,
                )
                if attempt < retries:
                    time.sleep(attempt * 2)
                continue

            kind, capture = self._easypay_verify_capture(data, capture_id)
            if kind == "ok" and capture["payment_id"] == (
                self._easypay_payment_reference()
            ):
                status = const.CAPTURE_STATUS_MAP.get(capture["status"])
                if status:
                    self.easypay_capture_status = status
                if status in ("paid", "captured", "failed"):
                    self._apply_payment_state(status, {})
                    return
            if attempt < retries:
                time.sleep(attempt * 2)

        _logger.warning(
            "Capture status not final after %d retries for %s — webhook will confirm.",
            retries,
            self.reference,
        )
        self._set_pending(extra_allowed_states=("authorized",))

    def _easypay_capture(self, capture_ref, *, idempotency_key=None):
        """POST /2.0/capture/{capture_ref}, store transaction ID, return response

        :param str idempotency_key: Optional EasyPay Idempotency-Key header
            value; EasyPay replays the stored response for a repeated key.
        """
        response = self.provider_id._easypay_make_request(
            f"/2.0/capture/{capture_ref}",
            {
                "descriptive": self.reference,
                "transaction_key": self.reference,
                "value": self.amount,
            },
            idempotency_key=idempotency_key,
        )
        self.provider_id._easypay_raise_for_status(response, "capture")
        capture_id = response.get("id")
        if not isinstance(capture_id, str) or not capture_id:
            raise const.EasyPayTransportError(
                _("EasyPay capture acknowledgement did not include an ID.")
            )
        self.easypay_transaction_id = capture_id
        return response

    def _easypay_operation_key(self, operation, attempt=0):
        """Deterministic EasyPay Idempotency-Key for a local operation.

        Same key on every retry of the same attempt so EasyPay replays the
        stored response instead of processing the request twice.
        """
        return hmac_tool(
            self.env(su=True),
            "easypay_operation",
            f"{self.id}|{self.reference}|{operation}|{attempt}",
        )[:50]

    def _easypay_lock_operation(self):
        """Row-lock this transaction for the duration of the request.

        Serializes concurrent capture/void/session submissions; a racing
        writer raises a serialization error that Odoo's request retry
        resolves.
        """
        self.ensure_one()
        self.env.cr.execute(
            "SELECT id FROM payment_transaction WHERE id = %s FOR UPDATE",
            [self.id],
        )

    def _easypay_verify_capture(self, data, capture_id):
        """Verify an authenticated capture read against this transaction.

        Returns ("ok", {"status", "payment_id"}), ("retry", None) when the
        read is inconclusive, or ("conflict", None) when it belongs to a
        different capture, reference or amount.
        """
        if not isinstance(data, dict):
            return "retry", None
        remote_id = data.get("id")
        key = data.get("transaction_key")
        payment_id = data.get("payment_id")
        if (
            not remote_id
            or key is None
            or not isinstance(payment_id, str)
            or not payment_id
        ):
            return "retry", None
        if remote_id != capture_id or key != self.reference:
            return "conflict", None
        try:
            value = float(data.get("value"))
        except (TypeError, ValueError, OverflowError):
            return "retry", None
        if not math.isfinite(value):
            return "retry", None
        if self.currency_id.compare_amounts(value, self.amount):
            return "conflict", None
        status = data.get("status")
        return "ok", {
            "status": status if isinstance(status, str) else None,
            "payment_id": payment_id,
        }

    def _easypay_payment_reference(self):
        """Locally stored EasyPay payment id used to bind capture reads.

        A ``provider_reference`` equal to the checkout or capture id is
        legacy bad data — including a token-backed offline transaction that
        stored its capture UUID there — and never counts as a payment id;
        fall back to the token's provider reference instead.
        """
        ref = self.provider_reference
        if (
            ref
            and ref != self.easypay_checkout_id
            and ref != self.easypay_transaction_id
        ):
            return ref
        return self.token_id.provider_ref

    def _send_void_request(self, amount_to_void=None):
        """Send void request to EasyPay."""
        if self.provider_code != "easypay":
            return super()._send_void_request(amount_to_void=amount_to_void)

        self._easypay_lock_operation()
        if self.easypay_transaction_id or self.state != "authorized":
            return
        if self.easypay_void_id:
            # A submitted void is resolved asynchronously; a repeat Void
            # click refreshes its status instead of resubmitting — this
            # also covers a webhook lost before the POST committed.
            response = self.provider_id._easypay_make_request(
                f"/2.0/void/{self.easypay_void_id}", method="GET"
            )
            self._easypay_apply_void_status(response)
            return
        if not self.provider_reference:
            raise ValidationError(
                _("Cannot void: No EasyPay payment ID found for this transaction.")
            )
        response = self.provider_id._easypay_make_request(
            f"/2.0/void/{self.provider_reference}",
            {"descriptive": self.reference[:255]},
            idempotency_key=self._easypay_operation_key(
                "void", self.easypay_void_attempt
            ),
        )
        self.provider_id._easypay_raise_for_status(response, "void")
        void_id = response.get("id")
        if not isinstance(void_id, str) or not void_id:
            raise ValidationError(
                _("EasyPay void failed: missing void id in the response.")
            )
        # The authorisation stays valid until the void outcome is verified;
        # the transaction is cancelled only on verified success.
        self.easypay_void_id = void_id

    def _easypay_apply_void_status(self, data):
        """Apply an authenticated void resource read to this transaction.

        Returns "ok" once the outcome is known (or still legitimately
        pending), "retry" when the data is inconclusive, and "conflict"
        when the read returned a different void id.
        """
        self.ensure_one()
        if not isinstance(data, dict) or not data.get("id"):
            return "retry"
        if data["id"] != self.easypay_void_id:
            return "conflict"
        status = data.get("status")
        if status in ("pending", "processing"):
            return "ok"
        if status == "success":
            if self.state != "cancel":
                self._set_canceled()
            return "ok"
        if status == "failed":
            # The void failed: release the guard so staff can retry while
            # the authorisation stays valid. A new attempt key is minted
            # only now that the failure is verified — uncertain responses
            # keep reusing the same key.
            self.easypay_void_id = False
            self.easypay_void_attempt += 1
            return "ok"
        return "retry"
