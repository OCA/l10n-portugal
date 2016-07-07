# -*- coding: utf-8 -*-
# Copyright (C) 2012 Thinkopen Solutions, Lda. All Rights Reserved
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from openerp import api, models, fields, _


class AccountInvoiceRefund(models.TransientModel):
    _inherit = 'account.invoice.refund'

#     @api.model
#     def _get_description(self):
#         context = dict(self._context or {})
#         invoices_ids = context.get('invoices_ids', [])
#         invoices = self.env['account.invoice'].browse(invoices_ids)
#         return u''.join(invoice.number for invoice in invoices)

    force_open = fields.Boolean(
        string='Force Open',
        help=('Select to force the opening of this document, '
              'even if there are older drafts or created ones.\n'
              'It doesn\'t force opening if there are higher ones.'))
#     description = fields.Char(compute=_get_description)

    @api.multi
    def compute_refund(self, mode='refund'):
        context = dict(self._context or {})
        invoices_ids = context.get('active_ids')
        invoices = self.env['account.invoice'].browse(invoices_ids)

        if not all(invoice.company_id == invoice.journal_id.company_id
                   for invoice in invoices):
            msg = _('Company Journal is different of Invoice Company')
            raise UserWarning(msg)

        res = super(AccountInvoiceRefund, self).compute_refund(mode=mode)

        last_invoice = invoices[-1] if invoices else False
        inv_type = last_invoice.type if last_invoice else False
        xml_id = self.get_action_window(inv_type)
        if xml_id:
            result = self.env.ref('account.%s' % (xml_id)).read()[0]
            result['domain'] = [(field, op, value)
                                for (field, op, value) in res['domain']
                                if field == 'id']
            return result
        return True

    def get_action_window(self, inv_type):
        """
        Get action window for documents
        """
        if not inv_type:
            return False
        elif inv_type in ('out_refund', 'in_debit_note'):
            return 'action_invoice_tree1'
        elif inv_type == 'in_refund':
            return 'action_invoice_tree2'
        elif inv_type in ('out_invoice', 'simplified_invoice', 'debit_note'):
            return 'action_invoice_tree3'
        elif inv_type == 'in_invoice':
            return 'action_invoice_tree4'
