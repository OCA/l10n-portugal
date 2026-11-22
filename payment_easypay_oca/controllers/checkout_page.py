# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import json
import logging

from odoo import http
from odoo.http import request

from .checkout_session import find_owned_checkout_transaction

_logger = logging.getLogger(__name__)


class EasyPayCheckoutPageController(http.Controller):
    @http.route(
        "/payment/easypay/checkout",
        type="http",
        auth="public",
        csrf=False,
        save_session=False,
    )
    def checkout_page(self, **kwargs):
        """Dedicated page to host EasyPay checkout form."""
        session_id = kwargs.get("session_id")
        tx_sudo = find_owned_checkout_transaction(session_id)
        if not tx_sudo:
            _logger.warning(
                "Checkout page requested for unknown session %s", session_id
            )
            return request.redirect("/payment/status")

        # The manifest is the documented POST /2.0/checkout result stored
        # server-side when the session was created; a client-supplied copy
        # in the query string is never trusted.
        manifest = request.session.get("easypay_checkout_manifest")
        api_url = tx_sudo.provider_id._easypay_get_api_url()
        hide_details = tx_sudo.provider_id.easypay_hide_details

        # EasyPay SDK accepts 'pt_PT', 'es_ES', or 'en' (default: browser lang).
        odoo_lang = tx_sudo.partner_id.lang or "en"
        if odoo_lang.startswith("pt"):
            sdk_language = "pt_PT"
        elif odoo_lang.startswith("es"):
            sdk_language = "es_ES"
        else:
            sdk_language = "en"

        # Serialise the entire JS data object server-side; it is injected as
        # an escaped data attribute, never inside a <script> block.
        easypay_data_json = json.dumps(
            {
                "sessionId": session_id,
                "csrfToken": request.csrf_token(),
                "manifest": manifest,
                "apiUrl": api_url,
                "language": sdk_language,
                "hideDetails": hide_details,
            }
        )

        return request.render(
            "payment_easypay_oca.checkout_page",
            {"easypay_data_json": easypay_data_json},
        )
