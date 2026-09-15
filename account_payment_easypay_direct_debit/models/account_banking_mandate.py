# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.phone_validation.tools.phone_validation import (
    phone_get_region_data_for_number,
)

_logger = logging.getLogger(__name__)


class AccountBankingMandate(models.Model):
    _inherit = "account.banking.mandate"

    format = fields.Selection(
        selection_add=[("easypay", "EasyPay SEPA")],
        ondelete={"easypay": "set default"},
    )
    easypay_provider_id = fields.Many2one(
        comodel_name="payment.provider",
        string="EasyPay Provider",
        domain="[('code', '=', 'easypay'), ('company_id', '=', company_id)]",
        ondelete="restrict",
        check_company=True,
        readonly=True,
        help="EasyPay provider the mandate was registered with.",
    )
    easypay_token_id = fields.Many2one(
        comodel_name="payment.token",
        string="EasyPay Token",
        domain="[('provider_id.code', '=', 'easypay')]",
        help="Optional. Reuse an EasyPay authorization the customer already "
        "granted through the checkout (Direct Debit payment method) instead "
        "of registering a new mandate with EasyPay.",
    )
    easypay_frequent_id = fields.Char(
        string="EasyPay Frequent Payment ID",
        readonly=True,
        copy=False,
        help="EasyPay frequent payment used as the debit target for "
        "captures under this mandate.",
    )
    easypay_mandate_ref = fields.Char(
        string="EasyPay Mandate Reference",
        readonly=True,
        copy=False,
        help="The SEPA mandate reference returned by EasyPay.",
    )
    easypay_mandate_state = fields.Char(
        string="EasyPay Mandate Status",
        readonly=True,
        copy=False,
        help="Latest mandate status reported by EasyPay.",
    )

    def validate(self):
        # Register EasyPay mandates with the API before they become valid;
        # a registration failure blocks validation.
        for mandate in self.filtered(lambda m: m.format == "easypay"):
            mandate._easypay_register()
        return super().validate()

    def _easypay_register(self):
        """Register the mandate with EasyPay as a frequent payment.

        Skipped when a frequent payment is already known (registered
        earlier) or when a checkout token is linked — its provider_ref is
        reused as the capture target.
        """
        self.ensure_one()
        if self.easypay_frequent_id:
            return
        if self.easypay_token_id:
            self.write(
                {
                    "easypay_frequent_id": self.easypay_token_id.provider_ref,
                    "easypay_provider_id": self.easypay_token_id.provider_id.id,
                }
            )
            return
        provider = self._easypay_get_provider()
        payload = {
            "method": "dd",
            "key": self.unique_mandate_reference,
            "customer": self._easypay_customer_data(),
            "sdd_mandate": self._easypay_sdd_mandate_data(),
        }
        response = provider._easypay_make_request("/2.0/frequent", payload)
        provider._easypay_raise_for_status(response, "mandate registration")
        method = response.get("method") or {}
        sdd_mandate = method.get("sdd_mandate") or {}
        if not response.get("id"):
            raise UserError(
                _(
                    "EasyPay mandate registration for '%(ref)s' returned no "
                    "frequent payment ID.",
                    ref=self.unique_mandate_reference,
                )
            )
        self.write(
            {
                "easypay_frequent_id": response["id"],
                "easypay_mandate_ref": sdd_mandate.get("id")
                or sdd_mandate.get("reference_adc"),
                "easypay_mandate_state": method.get("status"),
                "easypay_provider_id": provider.id,
            }
        )

    def _easypay_get_provider(self):
        """Return the EasyPay provider for this mandate."""
        self.ensure_one()
        provider = (
            self.easypay_provider_id
            or self.easypay_token_id.provider_id
            or self.env["payment.provider"].search(
                [
                    ("code", "=", "easypay"),
                    ("company_id", "=", self.company_id.id),
                    ("state", "!=", "disabled"),
                ],
                limit=1,
            )
        )
        if not provider:
            raise UserError(
                _(
                    "No active EasyPay provider found for company '%(company)s'.",
                    company=self.company_id.display_name,
                )
            )
        return provider

    def _easypay_refresh_state(self, provider):
        """Refresh the stored mandate status from EasyPay."""
        self.ensure_one()
        if not self.easypay_frequent_id:
            return
        try:
            data = provider._easypay_make_request(
                f"/2.0/frequent/{self.easypay_frequent_id}", method="GET"
            )
        except Exception:
            _logger.exception(
                "Could not refresh EasyPay mandate status for %s",
                self.easypay_frequent_id,
            )
            return
        status = (data.get("method") or {}).get("status")
        if status:
            self.easypay_mandate_state = status
        if status == "deleted":
            raise UserError(
                _(
                    "EasyPay mandate '%(ref)s' (%(id)s) is deleted and cannot "
                    "be used for new debits.",
                    ref=self.unique_mandate_reference,
                    id=self.easypay_frequent_id,
                )
            )

    def _easypay_customer_data(self):
        """Build the EasyPay customer object from the mandate's partner."""
        self.ensure_one()
        partner = self.partner_id
        language_code = (partner.lang or "en")[:2].upper()
        return {
            "name": partner.name or "",
            "email": partner.email or "",
            "key": str(partner.id),
            "language": language_code,
        }

    def _easypay_sdd_mandate_data(self):
        """Build the EasyPay sdd_mandate object.

        EasyPay requires iban, name, email, phone and account_holder — the
        partner's email and phone are therefore mandatory.
        """
        self.ensure_one()
        partner = self.partner_id
        missing = []
        if not partner.email:
            missing.append(_("email"))
        if not self._easypay_partner_phone():
            missing.append(_("phone"))
        if missing:
            raise UserError(
                _(
                    "Cannot register EasyPay mandate '%(ref)s': partner "
                    "'%(partner)s' is missing %(fields)s, required by EasyPay.",
                    ref=self.unique_mandate_reference,
                    partner=partner.display_name,
                    fields=", ".join(missing),
                )
            )
        account_holder = self.partner_bank_id.acc_holder_name or partner.name or ""
        data = {
            "iban": self.partner_bank_id.sanitized_acc_number,
            "name": account_holder,
            "account_holder": account_holder,
            "email": partner.email,
            "phone": self._easypay_partner_phone(),
            "key": self.unique_mandate_reference,
        }
        if partner.country_id:
            data["country_code"] = partner.country_id.code
        return data

    def _easypay_partner_phone(self):
        """Return the partner's phone number without country code."""
        self.ensure_one()
        partner = self.partner_id
        phone = partner.phone or partner.mobile or ""
        if not phone:
            return ""
        region = phone_get_region_data_for_number(phone)
        return region["national_number"] or phone
