# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    def _easypay_frequent_method_codes(self):
        # SEPA Direct Debit mandates act as the token: 'dd' checkouts must
        # always be created as 'frequent' payments.
        return super()._easypay_frequent_method_codes() | {"dd"}
