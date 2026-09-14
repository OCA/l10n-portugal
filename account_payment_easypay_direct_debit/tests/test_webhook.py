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
        cls.capture_request = {}

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
                return {
                    "id": "freq-uuid-1",
                    "currency": cls.company.currency_id.name,
                    "method": {"type": "dd", "status": "active"},
                }
            if endpoint.startswith("/2.0/single/") and method == "GET":
                return {}
            if endpoint.startswith("/2.0/capture/"):
                if method == "GET":
                    return {
                        "id": "cap-uuid-1",
                        "payment_id": "freq-uuid-1",
                        "transaction_key": cls.capture_request["transaction_key"],
                        "value": cls.capture_request["value"],
                        "status": cls.capture_status,
                    }
                cls.capture_request = payload.copy()
                return {"status": "ok", "id": "cap-uuid-1"}
            raise AssertionError(f"Unexpected API call {method} {endpoint}")

        patcher = patch.object(
            type(cls.provider),
            "_easypay_make_request",
            autospec=True,
            side_effect=_fake_make_request,
        )
        cls.mock_api = patcher.start()
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

    def _create_tx(self, *, upload=True):
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
        if upload:
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
        self.assertFalse(tx.token_id)
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
        self.assertEqual(tx.provider_reference, self.mandate.easypay_frequent_id)
        # Idempotent: posting the same webhook again changes nothing
        capture_id = tx.easypay_transaction_id
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
        self.assertEqual(tx.easypay_transaction_id, capture_id)

    def test_webhook_inconclusive_capture_leaves_debit_pending(self):
        """A claimed settlement cannot override an inconclusive API read."""
        tx = self._create_tx()
        # API reports an unrecognized status → the read is inconclusive
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
        self.assertEqual(response.status_code, 503)
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "pending")

    def test_upload_uses_capture_recovered_by_webhook(self):
        """A capture recorded by webhook is reused instead of resent."""
        tx = self._create_tx(upload=False)
        order = tx.payment_order_id
        # Model a lost upload acknowledgement: EasyPay accepted the
        # capture but the response never arrived locally, so the
        # reservation stays draft until the webhook records it.
        self.__class__.capture_request = {
            "transaction_key": tx.reference,
            "value": tx.amount,
        }
        self.__class__.capture_status = "paid"
        try:
            response = self._post_webhook(
                {
                    "key": tx.reference,
                    "id": "cap-uuid-1",
                    "type": "capture",
                    "status": "success",
                }
            )
            self.assertEqual(response.status_code, 200)
            tx.invalidate_recordset()
            self.assertEqual(tx.state, "done")
            self.assertEqual(tx.easypay_transaction_id, "cap-uuid-1")
            amount_before = tx.amount
            posts_before = len(self.mock_api.call_args_list)
            order.generated2uploaded()
            self.assertEqual(order.state, "uploaded")
            new_capture_posts = [
                call
                for call in self.mock_api.call_args_list[posts_before:]
                if len(call.args) > 1
                and call.args[1].startswith("/2.0/capture/")
                and call.kwargs.get("method", "POST") == "POST"
            ]
            self.assertFalse(new_capture_posts)
            tx.invalidate_recordset()
            self.assertEqual(tx.easypay_transaction_id, "cap-uuid-1")
            self.assertEqual(tx.amount, amount_before)
        finally:
            self.__class__.capture_status = "pending"
            self.__class__.capture_request = {}
