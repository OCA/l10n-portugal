# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import hashlib
import json
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.phone_validation.tools.phone_validation import (
    phone_get_region_data_for_number,
)


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
    easypay_registration_prepared_at = fields.Datetime(
        string="EasyPay Registration Prepared At",
        readonly=True,
        copy=False,
        help="When the standalone EasyPay registration was prepared. "
        "Validation must happen within 23 hours of this timestamp.",
    )
    easypay_registration_fingerprint = fields.Char(
        string="EasyPay Registration Fingerprint",
        readonly=True,
        copy=False,
        help="Digest of the provider and payload frozen at preparation "
        "time; validation refuses to send a different request.",
    )
    easypay_registration_recovery_id = fields.Char(
        string="EasyPay Registration Recovery ID",
        copy=False,
        groups="base.group_system",
        help="EasyPay frequent payment ID used to recover an ambiguous "
        "registration instead of posting a new one. Administrators only.",
    )

    def validate(self):
        # Local prerequisites are checked by super() before any network
        # call; the savepoint rolls everything back when registration
        # fails, including direct calls that bypass the form.
        with self.env.cr.savepoint():
            result = super().validate()
            for mandate in self.filtered(lambda m: m.format == "easypay"):
                mandate._easypay_register()
            return result

    def action_easypay_prepare_registration(self):
        """Prepare a standalone EasyPay mandate registration.

        Freezes the provider and the registration payload into a
        fingerprint, and starts the 23-hour window in which Validate may
        post to EasyPay. Nothing is sent here; preparing again with
        unchanged inputs is a no-op.
        """
        self.ensure_one()
        self.check_access("write")
        self.env.cr.execute(
            "SELECT id FROM account_banking_mandate WHERE id = %s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset()
        if (
            self.format != "easypay"
            or self.state != "draft"
            or self.easypay_frequent_id
            or self.easypay_token_id
        ):
            raise UserError(
                _(
                    "Only a draft EasyPay mandate without a registered "
                    "frequent payment or token can be prepared for "
                    "registration."
                )
            )
        provider = self._easypay_get_provider()
        self._easypay_check_provider(provider)
        # _check_valid_state() only constrains 'valid' records, so the
        # prerequisites it guards are checked explicitly here.
        if not self.signature_date or not self.partner_bank_id:
            raise UserError(
                _(
                    "Cannot prepare EasyPay mandate '%(ref)s': a signature "
                    "date and a bank account are required.",
                    ref=self.unique_mandate_reference,
                )
            )
        payload = self._easypay_registration_payload()
        digest = self._easypay_registration_digest(provider, payload)
        if self.easypay_registration_prepared_at:
            if self.easypay_registration_fingerprint != digest:
                raise UserError(
                    _(
                        "EasyPay mandate '%(ref)s' was prepared with "
                        "different parameters and cannot be prepared "
                        "again.",
                        ref=self.unique_mandate_reference,
                    )
                )
            return True
        # Bypass the write guard: only this action sets these fields.
        super().write(
            {
                "easypay_provider_id": provider.id,
                "easypay_registration_prepared_at": fields.Datetime.now(),
                "easypay_registration_fingerprint": digest,
            }
        )
        return True

    def write(self, vals):
        # The preparation timestamp and fingerprint are set only through
        # action_easypay_prepare_registration, which validates inputs.
        if (
            "easypay_registration_prepared_at" in vals
            or "easypay_registration_fingerprint" in vals
        ):
            raise UserError(
                _(
                    "The EasyPay registration preparation can only be set "
                    "by 'Prepare EasyPay Registration'."
                )
            )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                "easypay_registration_prepared_at" in vals
                or "easypay_registration_fingerprint" in vals
            ):
                raise UserError(
                    _(
                        "The EasyPay registration preparation can only be "
                        "set by 'Prepare EasyPay Registration'."
                    )
                )
        return super().create(vals_list)

    def unlink(self):
        self.check_access("unlink")
        if self.filtered("easypay_registration_prepared_at"):
            raise UserError(
                _(
                    "EasyPay mandates that were prepared for registration "
                    "cannot be deleted; cancel them instead."
                )
            )
        return super().unlink()

    def _easypay_register(self):
        """Register the mandate with EasyPay as a frequent payment.

        Skipped when a frequent payment is already known (registered
        earlier) or when a checkout token is linked — its provider_ref is
        reused as the capture target. Standalone registrations must have
        been prepared first, within the last 23 hours, with unchanged
        inputs; an administrator may instead supply a recovery ID for a
        frequent payment EasyPay already accepted.
        """
        self.ensure_one()
        if self.easypay_frequent_id:
            return
        if self.easypay_token_id:
            self._easypay_check_token()
            token = self.easypay_token_id
            self.write(
                {
                    "easypay_frequent_id": token.provider_ref,
                    "easypay_provider_id": token.provider_id.id,
                }
            )
            self._easypay_refresh_state(token.provider_id, verify_iban=True)
            return
        provider = self._easypay_get_provider()
        self._easypay_check_provider(provider)
        prepared_at = self.easypay_registration_prepared_at
        if not prepared_at:
            raise UserError(
                _(
                    "EasyPay mandate '%(ref)s' must be prepared for "
                    "registration first.",
                    ref=self.unique_mandate_reference,
                )
            )
        payload = self._easypay_registration_payload()
        if self.easypay_registration_fingerprint != (
            self._easypay_registration_digest(provider, payload)
        ):
            raise UserError(
                _(
                    "EasyPay mandate '%(ref)s' was prepared with different "
                    "parameters and cannot be registered; recreate the "
                    "mandate.",
                    ref=self.unique_mandate_reference,
                )
            )
        # Read the admin-only field only for admins to avoid a field
        # access error for regular accounting users.
        recovery_id = (
            self.easypay_registration_recovery_id
            if self.env.user.has_group("base.group_system")
            else False
        )
        if recovery_id:
            self._easypay_recover_registration(provider, recovery_id)
            return
        if fields.Datetime.now() >= prepared_at + timedelta(hours=23):
            raise UserError(
                _(
                    "The EasyPay registration window has expired for "
                    "mandate '%(ref)s'. Reconcile the registration in "
                    "EasyPay before retrying.",
                    ref=self.unique_mandate_reference,
                )
            )
        # Deterministic key: a retry of the same mandate replays EasyPay's
        # stored response instead of registering a second frequent payment.
        idempotency_key = hashlib.sha256(
            f"dd-mandate:{self.company_id.id}:{self.id}:"
            f"{self.unique_mandate_reference}".encode()
        ).hexdigest()[:50]
        # sudo: easypay_api_key is restricted to base.group_system; the
        # provider identity was validated above.
        response = provider.sudo()._easypay_make_request(
            "/2.0/frequent", payload, idempotency_key=idempotency_key
        )
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

    def _easypay_registration_payload(self):
        """Build the EasyPay frequent-payment payload for this mandate."""
        self.ensure_one()
        return {
            "method": "dd",
            "key": self.unique_mandate_reference,
            "customer": self._easypay_customer_data(),
            "sdd_mandate": self._easypay_sdd_mandate_data(),
        }

    def _easypay_registration_digest(self, provider, payload):
        """Fingerprint the inputs frozen by the preparation step."""
        self.ensure_one()
        return hashlib.sha256(
            json.dumps(
                [
                    provider.id,
                    provider.state,
                    provider.easypay_account_id,
                    payload,
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()

    def _easypay_recover_registration(self, provider, recovery_id):
        """Adopt an EasyPay frequent payment that already exists.

        Used when the original registration response was lost: the
        provider must confirm the frequent payment carries this
        mandate's key, an active dd method and the same mandate IBAN,
        so no second POST is needed.
        """
        self.ensure_one()
        recovery_id = (recovery_id or "").strip()
        if not re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
            r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            recovery_id,
        ):
            raise UserError(
                _(
                    "EasyPay recovery ID '%(rid)s' is not a valid "
                    "frequent payment ID.",
                    rid=recovery_id,
                )
            )
        # sudo: easypay_api_key is restricted to base.group_system; the
        # provider identity was validated by the caller.
        data = provider.sudo()._easypay_make_request(
            f"/2.0/frequent/{recovery_id}", method="GET"
        )
        method = data.get("method")
        sdd_mandate = method.get("sdd_mandate") if isinstance(method, dict) else {}
        remote_iban = "".join(
            str((sdd_mandate or {}).get("iban") or "").split()
        ).upper()
        local_iban = (self.partner_bank_id.sanitized_acc_number or "").upper()
        if not (
            isinstance(data, dict)
            and data.get("id") == recovery_id
            and data.get("key") == self.unique_mandate_reference
            and isinstance(method, dict)
            and str(method.get("type") or "").lower() == "dd"
            and method.get("status") == "active"
            and remote_iban
            and remote_iban == local_iban
        ):
            raise UserError(
                _(
                    "EasyPay could not confirm frequent payment "
                    "'%(rid)s' as the registration for mandate "
                    "'%(ref)s'.",
                    rid=recovery_id,
                    ref=self.unique_mandate_reference,
                )
            )
        self.write(
            {
                "easypay_frequent_id": recovery_id,
                "easypay_mandate_ref": (sdd_mandate or {}).get("id")
                or (sdd_mandate or {}).get("reference_adc"),
                "easypay_mandate_state": method.get("status"),
                "easypay_provider_id": provider.id,
                "easypay_registration_recovery_id": False,
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

    def _easypay_check_token(self):
        """Validate the checkout token before reusing its frequent payment."""
        self.ensure_one()
        token = self.easypay_token_id
        token.check_access("read")
        provider = token.provider_id
        if (
            not token.active
            or provider.code != "easypay"
            or provider.state not in ("test", "enabled")
            or provider.company_id != self.company_id
            or token.partner_id.commercial_partner_id
            != self.partner_id.commercial_partner_id
            or token.payment_method_id
            != self.env.ref("payment_easypay_oca.payment_method_easypay_direct_debit")
            or not token.provider_ref
        ):
            raise UserError(
                _(
                    "The EasyPay token linked to mandate '%(ref)s' cannot "
                    "be reused for direct debit.",
                    ref=self.unique_mandate_reference,
                )
            )

    def _easypay_check_provider(self, provider):
        """Validate a provider before an EasyPay call uses its API key."""
        self.ensure_one()
        if (
            not provider
            or provider.code != "easypay"
            or provider.company_id != self.company_id
            or provider.state not in ("test", "enabled")
        ):
            raise UserError(
                _(
                    "The EasyPay provider configured for mandate "
                    "'%(ref)s' is not usable.",
                    ref=self.unique_mandate_reference,
                )
            )

    def _easypay_refresh_state(self, provider, verify_iban=False):
        """Refresh the stored mandate status from EasyPay.

        :param verify_iban: also require the remote sdd_mandate IBAN to
            match this mandate's bank account (token-reuse path).
        """
        self.ensure_one()
        if not self.easypay_frequent_id:
            return
        self._easypay_check_provider(provider)
        # sudo: easypay_api_key is restricted to base.group_system; the
        # provider identity was validated above.
        data = provider.sudo()._easypay_make_request(
            f"/2.0/frequent/{self.easypay_frequent_id}", method="GET"
        )
        method = data.get("method")
        if not (
            data.get("id") == self.easypay_frequent_id
            and isinstance(method, dict)
            and str(method.get("type") or "").lower() == "dd"
            and method.get("status") == "active"
        ):
            raise UserError(
                _(
                    "EasyPay did not confirm an active direct debit mandate " "for %s.",
                    self.display_name,
                )
            )
        if verify_iban:
            remote_mandate = method.get("sdd_mandate") or {}
            remote_iban = "".join(str(remote_mandate.get("iban") or "").split()).upper()
            local_iban = (self.partner_bank_id.sanitized_acc_number or "").upper()
            if not remote_iban or remote_iban != local_iban:
                raise UserError(
                    _(
                        "EasyPay mandate for %(mandate)s is registered on a "
                        "different bank account.",
                        mandate=self.display_name,
                    )
                )
        self.easypay_mandate_state = "active"

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
