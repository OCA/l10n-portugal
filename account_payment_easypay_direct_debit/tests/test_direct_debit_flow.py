# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import _, fields
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.payment_easypay_oca.const import EasyPayTransportError


@tagged("-at_install", "post_install")
class TestDirectDebitFlow(AccountTestInvoicingCommon):
    """End-to-end flow: mandate → invoice → payment order → EasyPay debits.

    The EasyPay HTTP layer is mocked — no real requests are made.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.env.user.company_id = cls.company.id
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
        cls.payment_method = cls.env.ref(
            "account_payment_easypay_direct_debit."
            "account_payment_method_easypay_direct_debit"
        )
        cls.journal = cls.company_data["default_journal_bank"]
        cls.env["account.payment.method.line"].create(
            {
                "journal_id": cls.journal.id,
                "payment_method_id": cls.payment_method.id,
            }
        )
        cls.inbound_mode = cls.env["account.payment.mode"].create(
            {
                "name": "EasyPay Direct Debit",
                "bank_account_link": "variable",
                "payment_method_id": cls.payment_method.id,
                "company_id": cls.company.id,
                "easypay_provider_id": cls.provider.id,
            }
        )
        cls.inbound_mode.variable_journal_ids = cls.journal
        cls.product = cls.env["product.product"].create(
            {"name": "Test product", "type": "service"}
        )
        cls.invoice_line_account = cls.company_data["default_account_revenue"]
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "DD Customer",
                "email": "customer@example.com",
                "phone": "+351 911234567",
                "company_id": cls.company.id,
            }
        )
        cls.bank_account = cls.env["res.partner.bank"].create(
            {
                "partner_id": cls.partner.id,
                "acc_number": "PT50 0002 0123 1234 5678 9015 4",
            }
        )
        # Fake EasyPay API: registration + captures succeed by default.
        cls.capture_status = "pending"
        cls.capture_fail_for = set()  # payment ids to reject, for retry tests
        cls.capture_lost_for = set()  # payment ids whose response is lost
        cls.capture_request = {}
        cls.capture_amount_delta = 0
        cls.mandate_api_status = "active"

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
            if endpoint == "/2.0/frequent/freq-uuid-1" and method == "GET":
                return {
                    "id": "freq-uuid-1",
                    "method": {"type": "dd", "status": cls.mandate_api_status},
                }
            if endpoint.startswith("/2.0/capture/"):
                if method == "GET":
                    return {
                        "id": "cap-uuid-1",
                        "payment_id": "freq-uuid-1",
                        "transaction_key": cls.capture_request["transaction_key"],
                        "value": cls.capture_request["value"]
                        + cls.capture_amount_delta,
                        "status": cls.capture_status,
                    }
                if payload and payload.get("transaction_key") in cls.capture_lost_for:
                    raise EasyPayTransportError(_("Response lost"))
                if payload and payload.get("transaction_key") in cls.capture_fail_for:
                    raise UserError(_("EasyPay rejected the debit"))
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
                "partner_bank_id": cls.bank_account.id,
                "signature_date": "2026-01-01",
                "company_id": cls.company.id,
            }
        )
        cls.mandate.validate()

    def _create_invoice(self, amount=100.0):
        with Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        ) as invoice_form:
            invoice_form.partner_id = self.partner
            invoice_form.payment_mode_id = self.inbound_mode
            with invoice_form.invoice_line_ids.new() as line_form:
                line_form.product_id = self.product
                line_form.price_unit = amount
                line_form.tax_ids.clear()
        invoice = invoice_form.save()
        invoice.action_post()
        return invoice

    def _new_order_with(self, invoices):
        order = self.env["account.payment.order"].create(
            {
                "payment_type": "inbound",
                "payment_mode_id": self.inbound_mode.id,
                "journal_id": self.journal.id,
            }
        )
        self.env["account.invoice.payment.line.multi"].with_context(
            active_model="account.move", active_ids=invoices.ids
        ).create({}).run()
        return order

    def _upload_order(self, order):
        order.draft2open()
        order.open2generated()
        order.generated2uploaded()

    def test_full_flow(self):
        invoice1 = self._create_invoice(100.0)
        invoice2 = self._create_invoice(50.0)
        order = self._new_order_with(invoice1 + invoice2)
        self.assertEqual(len(order.payment_line_ids), 2)
        order.draft2open()
        # Same partner/bank/mandate → lines grouped in a single payment
        self.assertEqual(len(order.payment_ids), 1)
        payment = order.payment_ids
        self.assertEqual(payment.mandate_id, self.mandate)
        order.open2generated()
        self.assertEqual(order.state, "generated")
        order.generated2uploaded()
        self.assertEqual(order.state, "uploaded")
        # One EasyPay capture submitted for the grouped amount
        tx = payment.easypay_dd_transaction_ids
        self.assertEqual(len(tx), 1)
        self.assertEqual(tx.state, "pending")
        self.assertEqual(tx.operation, "offline")
        self.assertEqual(tx.easypay_transaction_id, "cap-uuid-1")
        self.assertEqual(tx.mandate_id, self.mandate)
        capture_calls = [
            c
            for c in self.mock_api.call_args_list
            if len(c.args) > 2
            and c.args[1].startswith("/2.0/capture/")
            and c.args[2].get("transaction_key") == tx.reference
        ]
        self.assertEqual(len(capture_calls), 1)
        self.assertEqual(capture_calls[0].args[2]["value"], 150.0)
        # Payment posted and invoice reconciled, as in the file flow
        self.assertEqual(payment.state, "in_process")
        self.assertIn(invoice1.payment_state, ("in_payment", "paid"))
        self.assertIn(invoice2.payment_state, ("in_payment", "paid"))

    def test_status_update_webhook(self):
        order = self._new_order_with(self._create_invoice())
        self._upload_order(order)
        tx = order.payment_ids.easypay_dd_transaction_ids
        tx._apply_payment_state("paid", {"status": "paid"})
        self.assertEqual(tx.state, "done")
        # Idempotent: same update again is a no-op
        tx._apply_payment_state("paid", {})
        self.assertEqual(tx.state, "done")

    def test_rejected_debit_creates_activity(self):
        order = self._new_order_with(self._create_invoice())
        self._upload_order(order)
        tx = order.payment_ids.easypay_dd_transaction_ids
        tx._apply_payment_state("rejected", {"status": "rejected"})
        self.assertEqual(tx.state, "cancel")
        # Post-processing (cron) schedules the manual-reversal activity
        tx._post_process()
        activity = order.activity_ids.filtered(
            lambda a: "direct debit" in (a.note or "")
        )
        self.assertTrue(activity)

    def test_cron_sync_pending(self):
        order = self._new_order_with(self._create_invoice())
        self._upload_order(order)
        tx = order.payment_ids.easypay_dd_transaction_ids
        self.__class__.capture_status = "paid"
        try:
            self.__class__.capture_amount_delta = 1
            self.env.cr.execute(
                "UPDATE payment_transaction"
                " SET create_date = create_date - interval '2 hours'"
            )
            self.env["payment.transaction"]._easypay_dd_cron_sync_pending()
            self.assertEqual(tx.state, "pending")
            self.__class__.capture_amount_delta = 0
            self.env["payment.transaction"]._easypay_dd_cron_sync_pending()
            self.assertEqual(tx.state, "done")
        finally:
            self.__class__.capture_status = "pending"
            self.__class__.capture_amount_delta = 0

    @mute_logger("odoo.tools.translate")
    def test_partial_failure_retry(self):
        order = self._new_order_with(self._create_invoice())
        order.draft2open()
        order.open2generated()
        payment = order.payment_ids
        # Force the capture to fail once
        key = payment._easypay_transaction_key()
        self.__class__.capture_fail_for.add(key)
        with self.assertRaises(UserError):
            order.generated2uploaded()
        self.assertEqual(order.state, "generated")
        # Retry: the failure flag is cleared, submission succeeds
        self.__class__.capture_fail_for.clear()
        order.generated2uploaded()
        self.assertEqual(order.state, "uploaded")
        self.assertEqual(payment.easypay_dd_transaction_ids.state, "pending")

    def _capture_post_count(self):
        return sum(
            1
            for call in self.mock_api.call_args_list
            if len(call.args) > 1
            and call.args[1].startswith("/2.0/capture/")
            and call.kwargs.get("method", "POST") == "POST"
        )

    def test_upload_blocks_inactive_remote_mandate(self):
        """A debit is not submitted while EasyPay reports the mandate inactive."""
        order = self._new_order_with(self._create_invoice())
        order.draft2open()
        order.open2generated()
        posts_before = self._capture_post_count()
        self.__class__.mandate_api_status = "pending"
        try:
            with self.assertRaises(UserError):
                order.generated2uploaded()
        finally:
            self.__class__.mandate_api_status = "active"
        self.assertEqual(order.state, "generated")
        self.assertEqual(self._capture_post_count(), posts_before)

    def test_upload_acknowledgement_does_not_settle_debit(self):
        """The capture POST acknowledgement is not a settlement."""
        order = self._new_order_with(self._create_invoice())
        self._upload_order(order)
        tx = order.payment_ids.easypay_dd_transaction_ids
        self.assertEqual(tx.state, "pending")

    def test_upload_rollback_reuses_reserved_debit(self):
        """Losing the capture response rolls back; retry reuses the debit."""
        order = self._new_order_with(self._create_invoice())
        order.draft2open()
        posts_before = self._capture_post_count()
        order.open2generated()
        payment = order.payment_ids
        tx_before = payment.easypay_dd_transaction_ids
        # Generate reserves the debit without submitting it to EasyPay.
        self.assertEqual(len(tx_before), 1)
        self.assertEqual(self._capture_post_count(), posts_before)
        key = payment._easypay_transaction_key()
        self.__class__.capture_lost_for.add(key)
        calls_before = len(self.mock_api.call_args_list)
        try:
            with self.assertRaises(UserError), self.env.cr.savepoint():
                order.generated2uploaded()
        finally:
            self.__class__.capture_lost_for.discard(key)
        # The rolled-back attempt must not disturb the reservation.
        payment.invalidate_recordset(["easypay_dd_transaction_ids"])
        self.assertEqual(payment.easypay_dd_transaction_ids, tx_before)
        self.assertFalse(tx_before.easypay_transaction_id)
        # The retry submits the same reservation with the same payload.
        order.generated2uploaded()
        self.assertEqual(order.state, "uploaded")
        payment.invalidate_recordset(["easypay_dd_transaction_ids"])
        tx_after = payment.easypay_dd_transaction_ids
        self.assertEqual(len(tx_after), 1)
        self.assertEqual(tx_after.id, tx_before.id)
        self.assertEqual(tx_after.state, "pending")
        capture_posts = [
            call
            for call in self.mock_api.call_args_list[calls_before:]
            if len(call.args) > 1
            and call.args[1].startswith("/2.0/capture/")
            and call.kwargs.get("method", "POST") == "POST"
        ]
        self.assertEqual(len(capture_posts), 2)
        self.assertEqual(capture_posts[0].args[1:3], capture_posts[1].args[1:3])
        self.assertTrue(capture_posts[0].kwargs.get("idempotency_key"))
        self.assertEqual(
            capture_posts[0].kwargs["idempotency_key"],
            capture_posts[1].kwargs["idempotency_key"],
        )

    def test_upload_after_reservation_deadline_does_not_submit(self):
        """A reservation past its deadline is never submitted to EasyPay."""
        order = self._new_order_with(self._create_invoice())
        order.draft2open()
        order.open2generated()
        posts_before = self._capture_post_count()
        with freeze_time(fields.Datetime.now() + timedelta(hours=24)):
            with self.assertRaises(UserError):
                order.generated2uploaded()
        self.assertEqual(order.state, "generated")
        self.assertEqual(self._capture_post_count(), posts_before)
