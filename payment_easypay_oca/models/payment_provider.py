# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging
from datetime import date, timedelta

import requests

from odoo import fields, models
from odoo.exceptions import ValidationError

from odoo.addons.phone_validation.tools.phone_validation import (
    phone_get_region_data_for_number,
)

from .. import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    code = fields.Selection(
        selection_add=[("easypay", "EasyPay")], ondelete={"easypay": "set default"}
    )
    easypay_account_id = fields.Char(
        string="Account ID",
        help="The Account ID provided by EasyPay",
    )
    easypay_api_key = fields.Char(
        string="API Key",
        help="The API Key provided by EasyPay",
        groups="base.group_system",
    )
    easypay_webhook_base_url = fields.Char(
        string="Webhook Base URL",
        help="Base URL that will be used for webhook configuration in EasyPay",
        compute="_compute_easypay_webhook_base_url",
    )
    easypay_hide_details = fields.Boolean(
        string="Hide Customer Details Form",
        help="When enabled, the EasyPay Checkout SDK hides the order details "
        "panel and shows a collapsible summary instead. ",
        default=False,
    )
    easypay_mb_expiration_days = fields.Integer(
        string="MB Expiration Days",
        help="Number of days before a Multibanco reference expires.",
        default=3,
    )
    easypay_mb_product = fields.Selection(
        selection=[("CHECKDIGIT", "CHECKDIGIT"), ("SPG", "SPG")],
        string="MB Product Type",
        help="The SPG product allows initiating refunds,"
        " but might have additional fees."
        " Please check with your Easypay account manager for details.",
        default="CHECKDIGIT",
        required=True,
    )

    # === COMPUTE METHODS ===#

    def _compute_feature_support_fields(self):
        """Override of `payment` to enable additional features."""
        res = super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == "easypay").update(
            {
                "support_manual_capture": "full_only",
                "support_refund": "partial",
                "support_tokenization": True,
            }
        )
        return res

    def _compute_easypay_webhook_base_url(self):
        """Compute the base URL that will be used for webhook configuration."""
        for provider in self:
            if provider.code == "easypay":
                provider.easypay_webhook_base_url = provider.get_base_url()
            else:
                provider.easypay_webhook_base_url = False

    # === BUSINESS METHODS - GETTERS ===#

    def _get_supported_currencies(self):
        """Override to restrict EasyPay to EUR only."""
        self.ensure_one()
        if self.code != "easypay":
            return super()._get_supported_currencies()
        return self.env["res.currency"].search([("name", "=", "EUR")])

    def _get_default_payment_method_codes(self):
        """Override of `payment` to return the default payment method codes."""
        if self.code != "easypay":
            return super()._get_default_payment_method_codes()
        # Return all supported EasyPay payment methods
        return {
            "card",  # Credit Card (pre-existing Odoo method)
            "multibanco",  # Multibanco (pre-existing Odoo method)
            "mbway",  # MBWAY (pre-existing Odoo method)
            "dd",  # EasyPay Direct Debit
            "vi",  # Virtual IBAN
            "ap",  # Apple Pay
            "gp",  # Google Pay
            "sw",  # Samsung Pay
            "easypay",  # Other payment methods (catch-all)
        }

    def _easypay_get_api_url(self):
        return const.API_URL_PROD if self.state == "enabled" else const.API_URL_TEST

    # === BUSINESS METHODS - PAYMENT FLOW ===#

    def _easypay_make_request(self, endpoint, payload=None, method="POST"):
        url = f"{self._easypay_get_api_url()}{endpoint}"
        headers = {
            "AccountId": self.easypay_account_id,
            "ApiKey": self.easypay_api_key,
            "Content-Type": "application/json",
        }

        try:
            response = requests.request(
                method,
                url,
                json=payload if method in ("POST", "PATCH") else None,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error("EasyPay API request failed: %s", e)
            raise ValidationError(
                self.env._("EasyPay API request failed: %s", str(e))
            ) from None

    def _easypay_raise_for_status(self, response, label="Request"):
        """Raise ValidationError if EasyPay response status is not 'ok'.

        :param dict response: The parsed API response
        :param str label: Short description for the error message (e.g. 'capture')
        :raise ValidationError: If response status != 'ok'
        """
        if response.get("status") != "ok":
            msg = response.get("message", ["Unknown error"])
            if isinstance(msg, list):
                msg = ", ".join(str(m) for m in msg)
            raise ValidationError(
                self.env._("EasyPay %(label)s failed: %(msg)s", label=label, msg=msg)
            )

    def _easypay_create_checkout_session(self, tx_sudo):
        """Create EasyPay checkout session for the transaction."""
        items = self._easypay_build_order_items(tx_sudo)

        # Map Odoo payment method code → EasyPay API method code(s).
        # When a specific method is selected, restrict the checkout to that
        # method only. The catch-all "easypay" (Other payment methods) sends
        # no filter so EasyPay shows all methods enabled on the account.
        odoo_pm_code = tx_sudo.payment_method_code
        easypay_code = const.EASYPAY_TO_ODOO.get(odoo_pm_code, odoo_pm_code)
        method_codes = [easypay_code] if easypay_code != "easypay" else []
        # SEPA DD mandates are always frequent — the mandate itself is the token.
        # For other methods, follow the tokenize flag.
        is_dd = odoo_pm_code == "sepa_direct_debit"
        is_frequent = is_dd or tx_sudo.tokenize

        # Build base payload
        payload = {
            "type": ["frequent" if is_frequent else "single"],
            "payment": {
                "currency": tx_sudo.currency_id.name,
                **({"methods": method_codes} if method_codes else {}),
            },
            "order": {
                "key": tx_sudo.reference,
                "value": tx_sudo.amount,
                "items": items,
            },
            "customer": self._easypay_build_customer_data(tx_sudo),
        }

        # Single payments require explicit capture config and payment type
        # Frequent payments must NOT include these fields per EasyPay API docs
        if not is_frequent:
            payload["payment"]["type"] = const.PAYMENT_TYPE_SALE
            payload["payment"]["capture"] = {
                "descriptive": tx_sudo.reference,
                "transaction_key": tx_sudo.reference,
            }

        # Multibanco: inject expiration_time and product into the payload
        if "mb" in method_codes:
            days = self.easypay_mb_expiration_days or 3
            expiry = date.today() + timedelta(days=days)
            payload["multibanco"] = {
                "expiration_time": f"{expiry.strftime('%Y-%m-%d')}T23:59:59Z",
                "product": self.easypay_mb_product or "CHECKDIGIT",
            }

        return self._easypay_make_request("/2.0/checkout", payload)

    def _easypay_build_order_items(self, tx_sudo):
        """Extract order items from transaction."""
        # Try to get items from sale order
        if tx_sudo.sale_order_ids:
            return [
                {
                    "description": line.product_id.name or line.name,
                    "quantity": int(line.product_uom_qty),
                    "key": str(line.id),
                    "value": float(line.price_total),
                }
                for line in tx_sudo.sale_order_ids[0].order_line
            ]

        if tx_sudo.invoice_ids:
            return [
                {
                    "description": line.product_id.name or line.name,
                    "quantity": int(line.quantity),
                    "key": str(line.id),
                    "value": float(line.price_total),
                }
                for line in tx_sudo.invoice_ids[0].invoice_line_ids
            ]

        # Fallback to generic payment item
        return [
            {
                "description": f"Payment for {tx_sudo.reference}",
                "quantity": 1,
                "key": tx_sudo.reference,
                "value": tx_sudo.amount,
            }
        ]

    def _easypay_build_customer_data(self, tx_sudo):
        """Build EasyPay customer payload from transaction partner."""
        phone = tx_sudo.partner_phone or ""
        phone_indicative = ""
        phone_number = phone

        if phone:
            region = phone_get_region_data_for_number(phone)
            if region["phone_code"] and region["national_number"]:
                phone_indicative = region["phone_code"]
                phone_number = region["national_number"]

        # ISO 639-1 Alpha-2 uppercase (e.g. "PT", "EN", "ES")
        # Odoo lang codes are like "pt_PT", "en_US" — take the first two chars.
        partner_lang = tx_sudo.partner_id.lang or "en"
        language_code = partner_lang[:2].upper()

        data = {
            "name": tx_sudo.partner_name or "",
            "email": tx_sudo.partner_email or "",
            "key": str(tx_sudo.partner_id.id),
            "language": language_code,
        }
        if phone_indicative:
            data["phone_indicative"] = phone_indicative
            data["phone"] = phone_number
        elif phone_number:
            data["phone"] = phone_number
        return data

    def action_easypay_sync_payment_methods(self):
        """Fetch available payment methods from EasyPay and update the provider."""
        self.ensure_one()
        if not self.easypay_account_id or not self.easypay_api_key:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "message": "Please fill in Account ID and API Key first.",
                    "type": "warning",
                    "sticky": False,
                },
            }
        config = self._easypay_make_request("/2.0/config", method="GET")
        api_codes = config.get("payment_methods") or []
        if not api_codes:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "message": "No payment methods returned by EasyPay.",
                    "type": "warning",
                    "sticky": False,
                },
            }
        # Translate EasyPay codes that need mapping, use others directly
        odoo_codes = [const.EASYPAY_TO_ODOO.get(code, code) for code in api_codes]
        api_methods = self.env["payment.method"].search([("code", "in", odoo_codes)])

        # Activate returned methods, deactivate all other EasyPay methods
        all_easypay_methods = self.env["payment.method"].search(
            [("code", "in", list(const.DEFAULT_PAYMENT_METHOD_CODES))]
        )

        # Deactivate all EasyPay methods first
        all_easypay_methods.write({"active": False})

        # Activate only the API returned methods
        api_methods.write({"active": True})

        # Set provider to use only active methods
        self.payment_method_ids = api_methods
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": (
                    f"Payment methods updated: {', '.join(m.name for m in api_methods)}"
                ),
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_easypay_test_connection(self):
        """Test connection to EasyPay API using ping endpoint."""
        self.ensure_one()

        if not self.easypay_account_id or not self.easypay_api_key:
            message = "Please fill in Account ID and API Key first."
            ntype = "warning"
            sticky = False
        else:
            ping = self._easypay_make_request("/2.0/system/ping", method="GET")
            env = ping.get("environment", "unknown")
            messages = [f"Connection successful! Environment: {env}."]
            ntype = "success"

            config = self._easypay_make_request("/2.0/config", method="GET")
            if config:
                base_url = self.get_base_url()
                generic_url = config.get("generic", "")
                if generic_url and not generic_url.startswith(base_url):
                    messages.append(
                        f"Webhook URLs point to a different host than '{base_url}'. "
                        f"Click 'Configure Webhooks' to update."
                    )
                    ntype = "warning"
                else:
                    messages.append("Webhook URLs are correctly configured.")

            message = "\n".join(messages)
            sticky = True

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": message,
                "type": ntype,
                "sticky": sticky or ntype == "danger",
            },
        }

    def action_easypay_configure_webhooks(self):
        if not self.easypay_api_key or not self.easypay_account_id:
            message = (
                "You cannot configure webhooks without setting your EasyPay API "
                "credentials first."
            )
            ntype = "danger"
        else:
            base_url = self.get_base_url()
            webhook_urls = {
                "generic": f"{base_url}/payment/easypay/webhook/generic",
                "authorisation": f"{base_url}/payment/easypay/webhook/authorisation",
                "transaction": f"{base_url}/payment/easypay/webhook/transaction",
            }
            try:
                self._easypay_make_request(
                    "/2.0/config", payload=webhook_urls, method="PATCH"
                )
                message = "Webhooks configured successfully!"
                ntype = "success"
            except Exception as e:
                _logger.exception("Error configuring webhooks: %s", e)
                message = (
                    "Error configuring webhooks. Please check your API credentials."
                )
                ntype = "danger"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": message,
                "type": ntype,
                "sticky": ntype == "danger",
            },
        }
