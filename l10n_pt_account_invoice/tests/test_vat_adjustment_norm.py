# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields
from odoo.tests import Form, common


class TestL10nPtAccountInvoice(common.TransactionCase):
    def setUp(self):
        super().setUp()
        # Exercise the invoice form as an accounting user.
        self.env.user.group_ids = [(4, self.env.ref("account.group_account_user").id)]
        self.AccountMove = self.env["account.move"]
        self.ResPartner = self.env["res.partner"]
        self.pt_country = self.env.ref("base.pt")
        self.partnerA = self.ResPartner.create(
            {
                "name": "Customer A",
                "country_id": self.pt_country.id,
                "city": "Porto",
                "zip": "2000-555",
            }
        )
        self.vendor = self.ResPartner.create(
            {
                "name": "Vendor A",
                "country_id": self.pt_country.id,
                "city": "Lisboa",
                "zip": "1000-001",
            }
        )

    def _new_refund_form(self, move_type, partner):
        return Form(
            self.AccountMove.with_context(
                default_move_type=move_type,
                default_partner_id=partner.id,
                default_invoice_date=fields.Date.today(),
            )
        )

    def test_refund_norm_selection(self):
        """A bookkeeper picks the same VAT adjustment legal basis — usable
        in both refund directions — on a customer and a vendor credit
        note; the choice and its note are stored on the moves."""
        self.env.company.account_fiscal_country_id = self.pt_country
        norm = self.env["l10n.pt.vat.adjustment.norm"].create(
            {
                "name": "Rectificação global",
                "note": "Art. 78.º-C do CIVA",
                "out_refunds": True,
                "in_refunds": True,
            }
        )

        form = self._new_refund_form("out_refund", self.partnerA)
        form.l10n_pt_vat_adjustment_norm_id = norm
        customer_refund = form.save()

        form = self._new_refund_form("in_refund", self.vendor)
        form.l10n_pt_vat_adjustment_norm_id = norm
        vendor_refund = form.save()

        for move in customer_refund + vendor_refund:
            self.assertEqual(move.l10n_pt_vat_adjustment_norm_id, norm)
            self.assertEqual(move.l10n_pt_vat_adjustment_norm_note, norm.note)
