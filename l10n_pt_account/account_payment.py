# -*- coding: utf-8 -*-

from openerp import models, fields, api, _

from openerp.addons.account.models.account_payment import MAP_INVOICE_TYPE_PARTNER_TYPE
MAP_INVOICE_TYPE_PARTNER_TYPE.update({
    'simplified_invoice': 'customer',
    'debit_note': 'customer',
    'in_debit_note': 'supplier',
})


class account_payment(models.Model):
    _inherit = "account.payment"

    @api.model
    def default_get(self, fields):
        """ Override method from account module
        We need to pass the needed fields to resolve_2many_commands, otherwise
        it burns and crashes when it tries to read the waybill_ids field
        if the user doesn't have the necessary permissions """
        rec = models.Model.default_get(self, fields)
        needed_fields = ['reference', 'currency_id', 'type', 'partner_id', 'residual']
        invoice_defaults = self.resolve_2many_commands(
            'invoice_ids', rec.get('invoice_ids'), fields=needed_fields)
        if invoice_defaults and len(invoice_defaults) == 1:
            invoice = invoice_defaults[0]
            rec['communication'] = invoice['reference']
            rec['currency_id'] = invoice['currency_id'][0]
            rec['payment_type'] = invoice['type'] in ('out_invoice', 'in_refund') and 'inbound' or 'outbound'
            rec['partner_type'] = MAP_INVOICE_TYPE_PARTNER_TYPE[invoice['type']]
            rec['partner_id'] = invoice['partner_id'][0]
            rec['amount'] = invoice['residual']
        return rec