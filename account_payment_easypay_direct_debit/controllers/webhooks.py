# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo.addons.payment_easypay_oca.controllers.webhooks import (
    EasyPayWebhookController,
)

_logger = logging.getLogger(__name__)


class EasyPayDirectDebitWebhookController(EasyPayWebhookController):
    """Fetch the authoritative status for direct debit captures.

    Direct debit webhooks match a ``payment.transaction`` (``operation``
    ``'offline'``) through the echoed transaction key, so the standard
    webhook flow applies — the only difference is the status endpoint:
    DD captures live under ``/2.0/capture/{id}``, not ``/2.0/single/``.
    """

    def _fetch_payment_data(self, tx_sudo):
        if not (tx_sudo._easypay_is_direct_debit() and tx_sudo.easypay_transaction_id):
            return super()._fetch_payment_data(tx_sudo)
        try:
            data = tx_sudo.provider_id._easypay_make_request(
                f"/2.0/capture/{tx_sudo.easypay_transaction_id}",
                method="GET",
            )
        except Exception:
            _logger.exception(
                "Error fetching EasyPay capture %s",
                tx_sudo.easypay_transaction_id,
            )
            return {}
        if not tx_sudo._easypay_dd_state_for_status(
            tx_sudo._easypay_dd_extract_status(data)
        ):
            # Unrecognized status — drop it so _resolve_status falls
            # back to the event-derived status.
            return {}
        return data
