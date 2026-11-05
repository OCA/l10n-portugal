# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
# Reference: https://github.com/bitmario/invoicexpress-api-python

import json
import logging
import pprint

import requests
from werkzeug.urls import url_join

from odoo import exceptions, models

_logger = logging.getLogger(__name__)


class InvoiceXpress(models.AbstractModel):
    _name = "account.invoicexpress"
    _inherit = "l10n_pt.invoice.provider"
    _description = "InvoiceXpress connector"

    _provider_code = "invoicexpress"

    def _get_config(self, company):
        account_name = company.invoicexpress_account_name
        api_key = company.invoicexpress_api_key
        if not account_name or not api_key:
            error_msg = self.env._(
                "Something went wrong on API key. You should check the field"
                " %(field:res.config.settings.invoicexpress_account_name)s in"
                " %(menu:base_setup.menu_config)s."
            )
            raise self.env["res.config.settings"].get_config_warning(error_msg)
        return {"account_name": account_name, "api_key": api_key}

    def _build_url(self, config, path):
        base_url = "https://{}.app.invoicexpress.com/".format(config["account_name"])
        return url_join(base_url, path)

    def _build_headers(self, config, headers_add=None):
        headers = {"content-type": "application/json", "accept": "application/json"}
        if headers_add:
            headers.update(headers_add)
        return headers

    def _build_params(self, config, params_add):
        params = {"api_key": config["api_key"]}
        if params_add:
            params.update(params_add)
        return params

    def _check_http_status(self, response):
        """
        You can perform up to 100 requests per minute for each Account. If you exceed
        this limit, you'll get a 429 Too Many Requests response for subsequent requests.

        We recommend you handle 429 responses so your integration retries requests
        automatically.
        """
        # TODO: implement request rate limit
        if response.status_code not in [200, 201]:
            errors = []
            json_data = None
            try:
                if response.content:
                    json_data = response.json()
                    errors = json_data.get("errors", [])
            except (ValueError, requests.exceptions.JSONDecodeError):
                # Response doesn't contain JSON, use text content or empty errors
                if response.text:
                    errors = [response.text]

            if isinstance(errors, list) and len(errors) > 0:
                msg = "\n".join(
                    "- " + (x.get("error") if isinstance(x, dict) else str(x))
                    for x in errors
                )
            elif isinstance(errors, dict):
                msg = errors.get("error", False) or repr(errors)
            elif json_data:
                # If we have JSON but no errors field, show the whole response
                msg = repr(json_data)
            else:
                # Handle empty responses or provide a more descriptive message
                msg = response.text or ""

            raise exceptions.ValidationError(
                self.env._(
                    "Error running API request (%(status_code)s %(reason)s):\n%(json)s",
                    status_code=response.status_code,
                    reason=response.reason,
                    json=msg,
                )
            )

    def call(
        self,
        company,
        endpoint,
        verb="GET",
        headers=None,
        params=None,
        payload=None,
        raise_errors=True,
    ):
        config = self._get_config(company)
        request_url = self._build_url(config, endpoint)
        request_headers = self._build_headers(config, headers)
        request_params = self._build_params(config, params)
        request_data = payload and json.dumps(payload) or ""
        _logger.debug(
            "\nRequest for %s %s:\n%s",
            request_url,
            verb,
            pprint.pformat(payload, indent=1),
        )
        response = requests.request(
            verb,
            request_url,
            params=request_params,
            data=request_data,
            headers=request_headers,
            timeout=15,
        )
        _logger.debug(
            "\nResponse %s: %s",
            response.status_code,
            pprint.pformat(response.json(), indent=1)
            if response.text.startswith("{")
            else response.text,
        )
        if raise_errors:
            self._check_http_status(response)
        return response

    # l10n_pt.invoice.provider contract

    def is_available(self, journal):
        company = journal.company_id
        return bool(
            company.has_invoicexpress
            and journal.invoicexpress_doc_type
            and journal.invoicexpress_doc_type != "none"
        )

    def can_email_document(self, journal):
        return bool(journal.company_id.invoicexpress_template_id)

    def get_document_type(self, document):
        doctype = document.journal_id.invoicexpress_doc_type
        if not doctype or doctype == "none":
            return
        if document.move_type == "out_refund":
            return "credit_note"
        return doctype

    def get_doc_prefix(self, doc_type):
        return {
            "invoice": "FT",
            "invoice_receipt": "FR",
            "simplified_invoice": "FS",
            "vat_moss_invoice": "FVM",
            # vat_moss_credit_note does not have a prefix!
            "credit_note": "NC",
            "debit_note": "ND",
        }.get(doc_type)

    def prepare_document_vals(self, document):
        return document._prepare_invoicexpress_vals()

    def create_document(self, document):
        doctype = document.l10n_pt_doc_type
        payload = document._prepare_invoicexpress_vals()
        response = self.call(
            document.company_id, f"{doctype}s.json", "POST", payload=payload
        ).json()
        values = response.get(doctype)
        if not values:
            raise exceptions.UserError(
                self.env._(
                    "Something went wrong: the InvoiceXpress response looks empty."
                )
            )
        document.l10n_pt_doc_id = values.get("id")
        document.l10n_pt_doc_permalink = values.get("permalink")
        response1 = self.call(
            document.company_id,
            f"{doctype}s/{document.l10n_pt_doc_id}/change-state.json",
            "PUT",
            payload={"invoice": {"state": "finalized"}},
            raise_errors=True,
        ).json()
        values1 = response1.get(doctype)
        seqnum = values1 and values1.get("inverted_sequence_number")
        if not seqnum:
            raise exceptions.UserError(
                self.env._(
                    "Something went wrong: the InvoiceXpress response"
                    " is missing a sequence number."
                )
            )
        prefix = self.get_doc_prefix(doctype)
        doc_number = f"{prefix} {seqnum}" if prefix else seqnum
        document.l10n_pt_doc_number = doc_number
        if document._name == "account.move":
            if document.payment_reference == document.name:
                document.payment_reference = doc_number
            document.name = doc_number
        document._l10n_pt_doc_post_message(self._description)

    def settle_document(self, document):
        doctype = document.l10n_pt_doc_type
        response = self.call(
            document.company_id,
            f"{doctype}s/{document.l10n_pt_doc_id}/change-state.json",
            "PUT",
            payload={"invoice": {"state": "settled"}},
            raise_errors=True,
        ).json()
        if not response.get(doctype, {}).get("inverted_sequence_number"):
            raise exceptions.UserError(
                self.env._(
                    "Something went wrong: the InvoiceXpress response"
                    " is missing a sequence number."
                )
            )
        document.message_post(
            body=self.env._("InvoiceXpress record has been modified to Paid.")
        )

    def email_document(self, document, ignore_no_config=False):
        doctype = document.l10n_pt_doc_type
        endpoint = f"{doctype}s/{document.l10n_pt_doc_id}/email-document.json"
        payload = document._prepare_invoicexpress_email_vals(ignore_no_config)
        if payload:
            self.call(document.company_id, endpoint, "PUT", payload=payload)
            document.message_post(
                body=self.env._(
                    "Email sent by InvoiceXpress:"
                    "<ul><li>To: %(email)s</li><li>Cc: %(cc)s</li></ul>",
                    email=payload["message"]["client"]["email"],
                    cc=payload["message"].get("cc", ""),
                )
            )

    def get_document_pdf(self, document):
        doctype = document.l10n_pt_doc_type
        response = self.call(
            document.company_id,
            f"{doctype}s/{document.l10n_pt_doc_id}.pdf",
            "GET",
            raise_errors=False,
        )
        if response.status_code == 200 and isinstance(response.content, bytes):
            return response.content
