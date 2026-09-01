# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import json
import logging

from markupsafe import Markup

from odoo import http
from odoo.http import request

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
        manifest_json = kwargs.get("manifest")

        if not session_id or not manifest_json:
            return request.redirect("/payment/status")

        try:
            manifest = json.loads(manifest_json)
        except json.JSONDecodeError:
            _logger.warning("Failed to parse checkout manifest from URL params")
            return request.redirect("/payment/status")

        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            ._find_easypay_transaction(session_id, None)
        )
        api_url = tx_sudo.provider_id._easypay_get_api_url() if tx_sudo else ""
        hide_details = tx_sudo.provider_id.easypay_hide_details if tx_sudo else False

        # EasyPay SDK accepts 'pt_PT', 'es_ES', or 'en' (default: browser lang).
        odoo_lang = (tx_sudo.partner_id.lang or "en") if tx_sudo else "en"
        if odoo_lang.startswith("pt"):
            sdk_language = "pt_PT"
        elif odoo_lang.startswith("es"):
            sdk_language = "es_ES"
        else:
            sdk_language = "en"

        # Serialise the entire JS data object server-side so the template
        # never interpolates untrusted strings inside a <script> block.
        easypay_data_json = Markup(
            json.dumps(
                {
                    "sessionId": session_id,
                    "manifest": manifest,
                    "apiUrl": api_url,
                    "language": sdk_language,
                    "hideDetails": hide_details,
                }
            )
        )

        return request.render(
            "payment_easypay_oca.checkout_page",
            {"easypay_data_json": easypay_data_json},
        )
