# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountPaymentMode(models.Model):
    _inherit = "account.payment.mode"

    easypay_provider_id = fields.Many2one(
        comodel_name="payment.provider",
        string="EasyPay Provider",
        domain="[('code', '=', 'easypay'), ('company_id', '=', company_id)]",
        ondelete="restrict",
        check_company=True,
        help="EasyPay provider used to submit direct debits for this payment "
        "mode. Its Account ID and API Key are used for all API calls.",
    )

    def _easypay_get_provider(self):
        """Return the EasyPay provider to use for this payment mode."""
        self.ensure_one()
        provider = self.easypay_provider_id or self.env["payment.provider"].search(
            [
                ("code", "=", "easypay"),
                ("company_id", "=", self.company_id.id),
                ("state", "!=", "disabled"),
            ],
            limit=1,
        )
        if not provider:
            raise UserError(
                _(
                    "No active EasyPay provider found for company '%(company)s'. "
                    "Configure one under Invoicing → Configuration → Payment "
                    "Providers, or set the EasyPay Provider on the payment "
                    "mode '%(mode)s'.",
                    company=self.company_id.display_name,
                    mode=self.display_name,
                )
            )
        return provider

    def action_easypay_test_connection(self):
        """Delegate to the provider's own connection test."""
        self.ensure_one()
        return self._easypay_get_provider().action_easypay_test_connection()
