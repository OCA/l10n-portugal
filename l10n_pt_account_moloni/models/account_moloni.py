# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
# Reference: https://www.moloni.pt/dev

import logging

import requests

from odoo import exceptions, fields, models

_logger = logging.getLogger(__name__)

BASE_URL = "https://api.moloni.pt/v1"


class AccountMoloni(models.AbstractModel):
    _name = "account.moloni"
    _inherit = "l10n_pt.invoice.provider"
    _description = "Moloni connector"

    _provider_code = "moloni"

    # -- Connection helpers -------------------------------------------------

    def _check_config(self, company):
        if not company.has_moloni:
            raise exceptions.UserError(
                self.env._("Moloni API configuration is missing on the company.")
            )

    def _get_access_token(self, company):
        self._check_config(company)
        now = fields.Datetime.now()
        if (
            company.moloni_access_token
            and company.moloni_token_expires_at
            and company.moloni_token_expires_at > now
        ):
            return company.moloni_access_token
        if company.moloni_refresh_token:
            token = self._grant(
                company,
                {
                    "grant_type": "refresh_token",
                    "refresh_token": company.moloni_refresh_token,
                },
                raise_errors=False,
            )
            if token:
                return token
        return self._grant(
            company,
            {
                "grant_type": "password",
                "username": company.moloni_username,
                "password": company.moloni_password,
            },
        )

    def _grant(self, company, payload, raise_errors=True):
        payload.update(
            {
                "client_id": company.moloni_client_id,
                "client_secret": company.moloni_client_secret,
            }
        )
        response = requests.post(f"{BASE_URL}/grant/", data=payload, timeout=15)
        data = response.status_code == 200 and response.json() or {}
        if not data.get("access_token"):
            if not raise_errors:
                return None
            raise exceptions.UserError(
                self.env._(
                    "Moloni authentication failed: %(error)s",
                    error=data.get("error_description") or response.text,
                )
            )
        company.sudo().write(
            {
                "moloni_access_token": data["access_token"],
                "moloni_refresh_token": data["refresh_token"],
                "moloni_token_expires_at": fields.Datetime.add(
                    fields.Datetime.now(),
                    seconds=int(data.get("expires_in", 3600)),
                ),
            }
        )
        return data["access_token"]

    def _check_http_status(self, response):
        if response.status_code != 200:
            raise exceptions.UserError(
                self.env._(
                    "Moloni request failed (%(code)s):\n%(msg)s",
                    code=response.status_code,
                    msg=response.text[:500],
                )
            )
        data = response.json()
        if isinstance(data, dict) and data.get("error"):
            raise exceptions.UserError(
                self.env._(
                    "Moloni request failed: %(msg)s",
                    msg=data.get("error_description") or data["error"],
                )
            )
        return data

    def call(self, company, endpoint, payload=None, raise_errors=True):
        token = self._get_access_token(company)
        url = f"{BASE_URL}/{endpoint}/?access_token={token}&_json=true"
        _logger.debug("Moloni %s: %s", url.split("?")[0], payload)
        response = requests.post(url, json=payload or {}, timeout=30)
        if not raise_errors:
            return response
        return self._check_http_status(response)

    # -- l10n_pt.invoice.provider contract ----------------------------------

    def is_available(self, journal):
        company = journal.company_id
        return bool(
            company.has_moloni
            and journal.moloni_doc_type
            and journal.moloni_doc_type != "none"
        )

    def get_document_type(self, document):
        doctype = document.journal_id.moloni_doc_type
        if not doctype or doctype == "none":
            return
        if document.move_type == "out_refund":
            return "creditNotes"
        return doctype

    def prepare_document_vals(self, document):
        return document._prepare_moloni_vals()

    def create_document(self, document):
        doctype = document.l10n_pt_doc_type
        payload = document._prepare_moloni_vals()
        # status=1 finalizes the document on insert
        data = self.call(document.company_id, f"{doctype}/insert", payload=payload)
        doc_id = data.get("document_id")
        if not doc_id:
            raise exceptions.UserError(
                self.env._("Moloni insert returned no document_id: %(data)s", data=data)
            )
        document.l10n_pt_doc_id = doc_id
        doc_data = (
            self.call(
                document.company_id,
                f"{doctype}/getOne",
                payload={"document_id": doc_id},
            )
            or {}
        )
        document.l10n_pt_doc_number = doc_data.get("number")
        if doc_data.get("permalink"):
            document.l10n_pt_doc_permalink = doc_data["permalink"]
        if document._name == "account.move" and document.l10n_pt_doc_number:
            if document.payment_reference == document.name:
                document.payment_reference = document.l10n_pt_doc_number
            document.name = document.l10n_pt_doc_number
        document._l10n_pt_doc_post_message(self._description)

    def get_document_pdf(self, document):
        data = self.call(
            document.company_id,
            "documents/getPdfLink",
            payload={"document_id": document.l10n_pt_doc_id},
            raise_errors=False,
        )
        url = data.json().get("url") if hasattr(data, "json") else None
        if not url:
            return
        pdf = requests.get(url, timeout=30)
        if pdf.status_code == 200 and pdf.content.startswith(b"%PDF"):
            return pdf.content

    def email_document(self, document, ignore_no_config=False):
        # Moloni has no per-document email template configuration
        # (provider email is capability-gated by can_email_document,
        # which stays False); standard Send & Print covers emailing.
        return
