# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Manual-entry E2E runner. Run with osh odoo shell as described in DEVELOP.md."""

# pylint: disable=print-used

import json
import os
import re
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from datetime import time as clock_time
from urllib.parse import urlencode, urlsplit
from uuid import UUID, uuid4

import requests

from odoo.tools.misc import hmac

API = "https://api.test.easypay.pt"
ROUTES = ("generic", "authorisation", "transaction")


class RunError(Exception):
    pass


def run(odoo_env):
    if os.getenv("EASYPAY_TEST_ALLOW_WRITES") != "1":
        raise RunError("Set EASYPAY_TEST_ALLOW_WRITES=1 to run the sandbox E2E test.")
    db = required("EASYPAY_TEST_E2E_DB")
    if odoo_env.cr.dbname != db or not db.endswith("-test"):
        raise RunError("Use a dedicated database ending in -test.")
    base = required("EASYPAY_TEST_WEBHOOK_BASE_URL").rstrip("/")
    url = urlsplit(base)
    if (
        url.scheme != "https"
        or not url.hostname
        or "." not in url.hostname
        or url.username is not None
        or url.hostname.endswith((".local", ".localhost"))
        or base != f"https://{url.netloc}"
    ):
        raise RunError("Use a public HTTPS origin for the webhook-only proxy.")
    local_port = int(os.getenv("EASYPAY_TEST_ODOO_PORT", "8177"))
    local = f"http://127.0.0.1:{local_port}"
    account = str(UUID(required("EASYPAY_TEST_CONFIG_ACCOUNT_UUID")))
    headers = {
        "AccountId": required("EASYPAY_TEST_ACCOUNT_ID"),
        "ApiKey": required("EASYPAY_TEST_API_KEY"),
    }
    provider_id = int(required("EASYPAY_TEST_PROVIDER_ID"))
    partner_id = int(required("EASYPAY_TEST_PARTNER_ID"))
    provider = odoo_env["payment.provider"].sudo().browse(provider_id).exists()
    partner = odoo_env["res.partner"].sudo().browse(partner_id).exists()
    currency = odoo_env.ref("base.EUR")
    if not (
        provider
        and provider.code == "easypay"
        and provider.state == "test"
        and provider.is_published
        and provider.easypay_account_id == headers["AccountId"]
        and provider.easypay_api_key == headers["ApiKey"]
        and provider.easypay_mb_expiration_days == 7
        and "multibanco" in provider.payment_method_ids.mapped("code")
        and partner
        and partner.country_id.code == "PT"
        and partner.email
        and partner.phone
        and partner.lang == "en_US"
        and currency.active
    ):
        raise RunError("Check the test provider and synthetic customer in DEVELOP.md.")

    reference = f"SANDBOX-MB-WEBHOOK-{uuid4().hex}"
    token = hmac(
        odoo_env(su=True), "generate_access_token", f"{partner.id}|10.0|{currency.id}"
    )
    checkout_url = (
        local
        + "/payment/pay?"
        + urlencode(
            {
                "reference": reference,
                "amount": "10.0",
                "currency_id": currency.id,
                "partner_id": partner.id,
                "company_id": provider.company_id.id,
                "access_token": token,
            }
        )
    )
    expected = {key: f"{base}/payment/easypay/webhook/{key}" for key in ROUTES}
    verify_proxy(base, expected)
    before = webhook_config(headers, account)
    if before == expected:
        raise RunError("The sandbox already points at this tunnel; restore it first.")
    with tempfile.NamedTemporaryFile(
        mode="w", prefix="easypay-e2e-webhooks-", suffix=".json", delete=False
    ) as backup:
        json.dump(before, backup)
        backup.flush()
        os.fsync(backup.fileno())
    print(f"Original webhook settings saved to {backup.name}", flush=True)

    try:
        api_request(headers, "PATCH", "/config", expected)
        if webhook_config(headers, account) != expected:
            raise RunError("EasyPay did not register all three webhook URLs.")
        first_day = date.today()
        issue_reference(checkout_url, provider_id)
        expiry_dates = {day + timedelta(days=7) for day in (first_day, date.today())}
        tx = read_transaction(odoo_env, reference, provider_id)
        if tx.state != "pending" or not tx.easypay_mb_reference:
            raise RunError(
                "Odoo did not record an issued, pending Multibanco reference."
            )
        payment_id = str(UUID(tx.provider_reference))
        capture_id = str(UUID(tx.easypay_transaction_id))
        payment = api_request(headers, "GET", f"/single/{payment_id}")
        method = payment["method"]
        expiries = {
            datetime.combine(day, clock_time(23, 59, 59), timezone.utc)
            for day in expiry_dates
        }
        expiry = datetime.fromisoformat(
            payment["multibanco"]["expiration_time"].replace("Z", "+00:00")
        )
        if not (
            payment["id"] == payment_id
            and payment["value"] == 10
            and payment["currency"] == "EUR"
            and payment["payment_status"] == "pending"
            and method["type"].lower() == "mb"
            and str(method["reference"]) == tx.easypay_mb_reference
            and expiry in expiries
        ):
            raise RunError(
                "EasyPay did not confirm the matching pending reference and expiry."
            )

        print(
            "Simulate payment at https://backoffice.test.easypay.pt/developers/payments\n"
            f"EUR 10.00 | Entity: {method['entity']} | "
            f"Reference: {method['reference']}\n"
            "Waiting up to five minutes for the webhook to settle Odoo...",
            flush=True,
        )
        wait_for_settlement(
            odoo_env, reference, provider_id, headers, payment_id, capture_id
        )
    finally:
        restore_webhook_config(headers, account, before, expected)
    print(
        f"PASS: {reference} was paid in EasyPay and moved from Pending to Done in Odoo."
    )


def required(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RunError(f"Set {name} before running the sandbox E2E test.")
    return value


def verify_proxy(base, urls):
    blocked = [base + "/", base + "/web/database/manager", *urls.values()]
    for url in blocked:
        response = requests.get(url, timeout=10, allow_redirects=False)
        if response.status_code != 404:
            raise RunError("The tunnel must block non-webhook paths.")
    for key, url in urls.items():
        response = requests.post(url, json=[], timeout=10, allow_redirects=False)
        if response.status_code != 400 or "malformed payload" not in response.text:
            raise RunError(f"The {key} webhook probe did not reach Odoo.")


def api_request(headers, method, path, payload=None):
    response = requests.request(
        method,
        API + "/2.0" + path,
        headers=headers,
        json=payload,
        timeout=15,
        allow_redirects=False,
    )
    if response.status_code != 200:
        raise RunError(
            f"EasyPay sandbox {method} returned HTTP {response.status_code}."
        )
    result = response.json()
    if not isinstance(result, dict):
        raise RunError("EasyPay returned an unexpected response.")
    return result


def webhook_config(headers, account):
    config = api_request(headers, "GET", "/config")
    if str(config.get("account", "")).strip().lower() != account:
        raise RunError("EasyPay returned an unexpected payment account UUID.")
    urls = {key: config.get(key) for key in ROUTES}
    if not all(isinstance(value, str) and value.strip() for value in urls.values()):
        raise RunError("Three existing webhook URLs are required for restoration.")
    return urls


def restore_webhook_config(headers, account, before, expected):
    current = webhook_config(headers, account)
    if current != before:
        if any(current[key] not in (before[key], expected[key]) for key in ROUTES):
            raise RunError(
                "Webhook settings changed externally. Check the saved backup."
            )
        api_request(headers, "PATCH", "/config", before)
        if webhook_config(headers, account) != before:
            raise RunError("Webhook restoration failed. Check the saved backup.")
    print("Verified that all three original webhook URLs are restored.", flush=True)


def issue_reference(url, provider_id):
    from playwright.sync_api import Error, sync_playwright

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(locale="en-US")
            page.set_default_timeout(20_000)
            page.goto(url, wait_until="domcontentloaded")
            page.locator(
                f'[data-provider-id="{provider_id}"][data-provider-state="test"]'
                '[data-payment-method-code="multibanco"]'
            ).check()
            page.locator('[name="o_payment_submit_button"]').click()
            page.wait_for_url("**/payment/easypay/checkout?**")
            frame = page.frame_locator(
                '#easypay-checkout iframe[src^="https://pay.sandbox.easypay.pt/"]'
            )
            advance = frame.get_by_role(
                "button", name=re.compile(r"^(Continue|Confirm|End)$", re.I)
            ).filter(visible=True)
            # The SDK can show pre-filled customer details before method selection.
            method = frame.get_by_alt_text("Multibanco", exact=True).filter(
                visible=True
            )
            method_selected = False
            for _ in range(5):
                try:
                    choice = advance if method_selected else method.or_(advance)
                    choice.first.wait_for(timeout=8_000)
                    if not method_selected and method.is_visible():
                        method.click()
                        method_selected = True
                    else:
                        advance.first.click()
                except Error:
                    if "/payment/status" in page.url:
                        break
                    raise
            page.wait_for_url("**/payment/status**")
            browser.close()
    except Error:
        raise RunError(
            "Browser checkout failed. Check Chromium and the EasyPay SDK UI."
        ) from None


def read_transaction(odoo_env, reference, provider_id):
    odoo_env.cr.rollback()
    odoo_env.invalidate_all(flush=False)
    tx = (
        odoo_env["payment.transaction"]
        .sudo()
        .search(
            [("reference", "=", reference), ("provider_id", "=", provider_id)], limit=2
        )
    )
    if len(tx) != 1:
        raise RunError("No unique Odoo transaction matched the checkout reference.")
    return tx


def wait_for_settlement(
    odoo_env, reference, provider_id, headers, payment_id, capture_id
):
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        tx = read_transaction(odoo_env, reference, provider_id)
        if tx.state not in ("pending", "done"):
            raise RunError("The Odoo transaction left pending without settling.")
        payment = api_request(headers, "GET", f"/single/{payment_id}")
        if payment.get("id") != payment_id:
            raise RunError("EasyPay returned a different payment.")
        if (
            tx.state == "done"
            and tx.easypay_capture_status == "paid"
            and payment.get("payment_status") == "paid"
            and any(
                capture.get("id") == capture_id and capture.get("status") == "success"
                for capture in payment.get("captures", [])
            )
        ):
            return
        time.sleep(3)
    raise RunError("Timed out waiting for EasyPay and Odoo to confirm settlement.")


if __name__ == "__main__":
    try:
        run(env)  # noqa: F821  (injected by osh odoo shell)
    except RunError as exc:
        sys.exit(str(exc))
    except KeyboardInterrupt:
        sys.exit("Interrupted.")
    except (
        AttributeError,
        ImportError,
        KeyError,
        TypeError,
        ValueError,
        requests.RequestException,
    ):
        sys.exit("Sandbox E2E failed. If in doubt, check the saved webhook backup.")
