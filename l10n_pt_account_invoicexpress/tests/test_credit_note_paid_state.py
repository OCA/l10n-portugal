from unittest.mock import patch

from odoo import fields
from odoo.tests import Form, common

from .invoicexpress_mock import mock_request_side_effect


@common.tagged("-at_install", "post_install")
class TestCreditNotePaidState(common.TransactionCase):
    """
    Regression test for https://github.com/OCA/l10n-portugal/issues/188

    InvoiceXpress marks Credit Notes as Paid as soon as they are issued,
    so when the customer refund is later reconciled in Odoo, the update
    to the Paid state is refused by InvoiceXpress. This must not block
    the payment reconciliation.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.write(
            {
                "invoicexpress_account_name": "ACCOUNT",
                "invoicexpress_api_key": "APIKEY",
                "country_id": self.env.ref("base.pt").id,
            }
        )
        Journal = self.env["account.journal"]
        self.sale_journal = Journal.search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        )
        self.bank_journal = Journal.search(
            [("type", "=", "bank"), ("company_id", "=", self.company.id)], limit=1
        )
        self.partner = self.env["res.partner"].create(
            {
                "name": "Customer A",
                "country_id": self.env.ref("base.pt").id,
                "city": "Porto",
                "zip": "2000-555",
            }
        )
        self.product = self.env["product.product"].create(
            {"name": "Product A", "list_price": "2.0"}
        )

    @patch("requests.request")
    def test_credit_note_refund_reconciled(self, mock_request):
        """
        A Credit Note refund payment can be reconciled even though the
        Credit Note was already marked Paid on InvoiceXpress when issued.
        """
        mock_request.side_effect = mock_request_side_effect
        # The sales journal is configured to use InvoiceXpress
        self.sale_journal.invoicexpress_doc_type = "invoice_receipt"
        # An invoice is issued and transmitted to InvoiceXpress
        invoice = self._create_invoice()
        self._flush_tracking()
        # The customer payment is registered and reconciled
        invoice_payment = self._register_payment(invoice)
        self._reconcile_statement_line(invoice_payment, invoice.amount_total)
        self._flush_tracking()
        self.assertEqual(invoice.payment_state, "paid")
        # A Credit Note is issued for the paid invoice and transmitted to
        # InvoiceXpress, where it is automatically marked Paid
        credit_note = invoice._reverse_moves()
        credit_note.action_post()
        self._flush_tracking()
        self.assertEqual(credit_note.move_type, "out_refund")
        self.assertEqual(credit_note.invoicexpress_doc_type, "credit_note")
        self.assertTrue(credit_note.invoicexpress_id)
        self.assertEqual(credit_note.payment_state, "not_paid")
        # The customer is refunded through a registered payment
        payment = self._register_payment(credit_note)
        # And the refund is reconciled with the bank statement
        self._reconcile_statement_line(payment, -credit_note.amount_total)
        self._flush_tracking()
        # The refused InvoiceXpress update does not block the reconciliation
        self.assertEqual(credit_note.payment_state, "paid")
        # The document was checked and found already Paid on InvoiceXpress
        check_calls = [
            c
            for c in mock_request.call_args_list
            if c.args[0] == "GET" and "credit_notes/" in c.args[1]
        ]
        self.assertTrue(check_calls)

    def _create_invoice(self):
        move_form = Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        )
        move_form.invoice_date = fields.Date.today()
        move_form.partner_id = self.partner
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product
        invoice = move_form.save()
        invoice.action_post()
        return invoice

    def _register_payment(self, move):
        return (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=move.ids)
            .create({})
            ._create_payments()
        )

    def _flush_tracking(self):
        # Tracked field callbacks run at commit time, when the transaction
        # is flushed; this is when the InvoiceXpress paid update is sent
        self.env.flush_all()
        self.cr.flush()

    def _reconcile_statement_line(self, payment, amount):
        statement_line = self.env["account.bank.statement.line"].create(
            {
                "payment_ref": payment.name,
                "journal_id": self.bank_journal.id,
                "partner_id": self.partner.id,
                "amount": amount,
            }
        )
        _st_liquidity, st_suspense, _st_other = statement_line._seek_for_lines()
        liquidity, _counterpart, _writeoff = payment._seek_for_lines()
        st_suspense.account_id = liquidity.account_id
        (st_suspense + liquidity).reconcile()
