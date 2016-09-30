# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./

from openerp import models, fields, api
from openerp.addons.l10n_pt_acount.report.amount_to_text_pt import amount_to_text
import json

from openerp.addons.account.models.account_payment \
    import MAP_INVOICE_TYPE_PARTNER_TYPE, MAP_INVOICE_TYPE_PAYMENT_SIGN
MAP_INVOICE_TYPE_PARTNER_TYPE.update({
    'simplified_invoice': 'customer',
    'debit_note': 'customer',
    'in_debit_note': 'supplier',
})

MAP_INVOICE_TYPE_PAYMENT_SIGN.update({
    'simplified_invoice': 1,
    'debit_note': 1,
    'in_debit_note': -1,
})


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.model
    def default_get(self, fields):
        """ Override method from account module
        We need to pass the needed fields to resolve_2many_commands, otherwise
        it burns and crashes when it tries to read the waybill_ids field
        if the user doesn't have the necessary permissions """
        rec = models.Model.default_get(self, fields)
        needed_fields = [
            'reference', 'currency_id', 'type', 'partner_id', 'residual']
        invoice_defaults = self.resolve_2many_commands(
            'invoice_ids', rec.get('invoice_ids'), fields=needed_fields)
        if invoice_defaults and len(invoice_defaults) == 1:
            invoice = invoice_defaults[0]
            rec['communication'] = invoice['reference']
            rec['currency_id'] = invoice['currency_id'][0]
            rec['payment_type'] = invoice['type'] in (
                'out_invoice', 'in_refund') and 'inbound' or 'outbound'
            rec['partner_type'] = MAP_INVOICE_TYPE_PARTNER_TYPE[
                invoice['type']]
            rec['partner_id'] = invoice['partner_id'][0]
            rec['amount'] = invoice['residual']
        return rec

    total_regulated = fields.Float(
        string="Total Regulated Amount", compute='_compute_total_regulated')

    @api.depends('invoice_ids')
    def _compute_total_regulated(self):
        for record in self:
            record.total_regulated = 0
            for invoice in record.invoice_ids:
                record.total_regulated += self.get_invoice_paid_amount(invoice)

    @api.multi
    def text_amount(self):
        currency_name = self.company_id.currency_id.name
        return amount_to_text(self.amount, 'pt', currency_name)

    @api.multi
    def get_invoice_paid_amount(self, invoice):
        data = json.loads(invoice.payments_widget)
        content = data['content']
        content = content[0]
        amount = content['amount']
        return amount
