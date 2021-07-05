# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
# Reference: https://github.com/bitmario/invoicexpress-api-python

import json
import logging
import pprint

import requests
from werkzeug.urls import url_join

from odoo import _, exceptions, models

_logger = logging.getLogger(__name__)


class InvoiceXpress(models.AbstractModel):
    _name = "account.invoicexpress"
    _description = "InvoiceXpress connector"

    def _get_config(self, company):
        account_name = company.invoicexpress_account_name
        api_key = company.invoicexpress_api_key
        if not account_name or not api_key:
            error_msg = _(
                """Something went wrong on API key. You should check the field
                %(field:res.config.settings.invoicexpress_account_name)s in
                %(menu:base_setup.menu_config)s."""
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
        this limit, you’ll get a 429 Too Many Requests response for subsequent requests.

        We recommend you handle 429 responses so your integration retries requests
        automatically.
        """
        # TODO: implement request rate limit
        if response.status_code not in [200, 201]:
            raise exceptions.ValidationError(
                _(
                    "Error running API request ({} {}): {}".format(
                        response.status_code, response.reason, response.text
                    )
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
        _logger.debug("\nRequest for %s %s:\n%s", request_url, verb, request_data)
        response = requests.request(
            verb,
            request_url,
            params=request_params,
            data=request_data,
            headers=request_headers,
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
