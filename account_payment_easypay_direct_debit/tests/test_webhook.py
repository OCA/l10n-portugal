# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("-at_install", "post_install")
class TestDirectDebitWebhook(HttpCase):
    """Webhook handling for direct debit payment transactions.

    DD captures are tracked as ``payment.transaction`` records, so the
    standard EasyPay webhook routes match them by reference — the only
    difference is the status endpoint (/2.0/capture/{id}).
    The EasyPay HTTP layer is mocked — no real requests are made.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env.user.groups_id |= cls.env.ref(
            "account_payment_order.group_account_payment"
        )
        cls.provider = cls.env["payment.provider"].create(
            {
                "name": "EasyPay Test",
                "code": "easypay",
                "state": "test",
                "company_id": cls.company.id,
                "easypay_account_id": "test-account-id",
                "easypay_api_key": "test-api-key",
            }
        )
        payment_method = cls.env.ref(
            "account_payment_easypay_direct_debit."
            "account_payment_method_easypay_direct_debit"
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.env["account.payment.method.line"].create(
            {
                "journal_id": cls.journal.id,
                "payment_method_id": payment_method.id,
            }
        )
        cls.inbound_mode = cls.env["account.payment.mode"].create(
            {
                "name": "EasyPay Direct Debit",
                "bank_account_link": "variable",
                "payment_method_id": payment_method.id,
                "company_id": cls.company.id,
                "easypay_provider_id": cls.provider.id,
                "variable_journal_ids": [(6, 0, cls.journal.ids)],
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "DD Customer",
                "email": "customer@example.com",
                "phone": "+351 911234567",
                "company_id": cls.company.id,
            }
        )
        bank_account = cls.env["res.partner.bank"].create(
            {
                "partner_id": cls.partner.id,
                "acc_number": "PT50 0002 0123 1234 5678 9015 4",
            }
        )
        # Fake EasyPay API: mandate registration + capture creation succeed;
        # status lookups return ``cls.capture_status``.
        cls.capture_status = "pending"

        def _fake_make_request(
            _provider, endpoint, payload=None, method="POST", **_kwargs
        ):
            if endpoint == "/2.0/frequent":
                return {
                    "status": "ok",
                    "id": "freq-uuid-1",
                    "method": {
                        "type": "dd",
                        "status": "active",
                        "sdd_mandate": {"id": "m-12345"},
                    },
                }
            if endpoint.startswith("/2.0/frequent/") and method == "GET":
                return {"method": {"status": "active"}}
            if endpoint.startswith("/2.0/capture/"):
                if method == "GET":
                    return {"status": cls.capture_status}
                return {"status": "ok", "id": "cap-uuid-1"}
            raise AssertionError(f"Unexpected API call {method} {endpoint}")

        patcher = patch.object(
            type(cls.provider),
            "_easypay_make_request",
            autospec=True,
            side_effect=_fake_make_request,
        )
        patcher.start()
        cls.addClassCleanup(patcher.stop)

        cls.mandate = cls.env["account.banking.mandate"].create(
            {
                "format": "easypay",
                "partner_bank_id": bank_account.id,
                "signature_date": "2026-01-01",
                "company_id": cls.company.id,
            }
        )
        cls.mandate.validate()

    def _create_tx(self):
        """Run an invoice through the DD order flow → payment.transaction."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "payment_mode_id": self.inbound_mode.id,
                "invoice_date": "2026-01-15",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Service",
                            "quantity": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        order = self.env["account.payment.order"].create(
            {
                "payment_type": "inbound",
                "payment_mode_id": self.inbound_mode.id,
                "journal_id": self.journal.id,
            }
        )
        self.env["account.invoice.payment.line.multi"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({}).run()
        order.draft2open()
        order.open2generated()
        order.generated2uploaded()
        return order.payment_ids.easypay_dd_transaction_ids

    def _post_webhook(self, payload, route="/payment/easypay/webhook/generic"):
        return self.url_open(
            route,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_webhook_empty_payload_is_noop(self):
        """Payloads without key or capture id get a bare 200."""
        response = self._post_webhook({"type": "capture"})
        self.assertEqual(response.status_code, 200)

    def test_webhook_unknown_key_is_noop(self):
        """Payloads matching no payment.transaction are ignored."""
        response = self._post_webhook({"key": "UNKNOWN-KEY", "id": "no-such"})
        self.assertEqual(response.status_code, 200)

    def test_webhook_updates_transaction_state(self):
        """A webhook matching a DD tx fetches the authoritative API status."""
        tx = self._create_tx()
        self.assertEqual(tx.state, "pending")
        self.__class__.capture_status = "paid"
        try:
            response = self._post_webhook(
                {"key": tx.reference, "id": tx.easypay_transaction_id}
            )
        finally:
            self.__class__.capture_status = "pending"
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")
        # Idempotent: posting the same webhook again changes nothing
        self.__class__.capture_status = "paid"
        try:
            response = self._post_webhook(
                {"key": tx.reference, "id": tx.easypay_transaction_id}
            )
        finally:
            self.__class__.capture_status = "pending"
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")

    def test_webhook_falls_back_to_event_status(self):
        """When the API sync yields nothing, the event status applies.

        Uses the nested transaction-webhook payload where the event
        status lives inside the 'transaction' object.
        """
        tx = self._create_tx()
        # API reports an unrecognized status → the event status applies
        self.__class__.capture_status = "mysterious"
        payload = {
            "transaction": {
                "key": tx.reference,
                "id": tx.easypay_transaction_id,
                "type": "capture",
                "status": "paid",
            }
        }
        try:
            response = self._post_webhook(
                payload, route="/payment/easypay/webhook/transaction"
            )
        finally:
            self.__class__.capture_status = "pending"
        self.assertEqual(response.status_code, 200)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")
