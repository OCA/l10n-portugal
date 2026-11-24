# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging

from odoo import SUPERUSER_ID, api
from odoo.fields import Command

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Unlink Direct Debit methods from EasyPay providers.

    Direct Debit is not implemented by this module: the sync action no
    longer links it and checkout rejects it. Providers that picked it up
    through an earlier sync (or manually) keep the method records — only
    the provider links are removed, never the rows themselves.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    providers = (
        env["payment.provider"]
        .with_context(active_test=False)
        .search([("code", "=", "easypay")])
    )
    if not providers:
        return

    local_dd = env.ref(
        "payment_easypay_oca.payment_method_easypay_direct_debit",
        raise_if_not_found=False,
    )
    core_dd = env.ref(
        "payment.payment_method_sepa_direct_debit",
        raise_if_not_found=False,
    )
    for method in (local_dd, core_dd):
        if not method:
            continue
        linked = providers.filtered(lambda p, m=method: m in p.payment_method_ids)
        if linked:
            _logger.info(
                "Unlinking %s from EasyPay providers %s",
                method.display_name,
                linked.mapped("name"),
            )
            linked.payment_method_ids = [Command.unlink(method.id)]
        if method == local_dd:
            # The local placeholder stays inactive; make sure no other
            # provider keeps it usable.
            if not method.provider_ids:
                method.active = False
