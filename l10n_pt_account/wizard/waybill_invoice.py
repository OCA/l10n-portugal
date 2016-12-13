# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from openerp import models, fields, api, _


class WaybillInvoice(models.TransientModel):
    _name = "waybill.invoice"
    _description = "Account PT Invoice Waybill"

    def _get_journal_id(self):
        vals = []
        journal_obj = self.env['account.journal']
        journals = journal_obj.search([('type', '=', 'sale')])
        return [(j.id, j.name) for j in journals]

    journal_id = fields.Selection(
        _get_journal_id, string='Destination Journal', required=True)
    group = fields.Boolean(string="Group by partner")
    invoice_date = fields.Date(string='Invoiced date')

    @api.model
    def view_init(self, fields_list):
        res = super(WaybillInvoice, self).view_init(fields_list)
        guia_obj = self.env['account.guia']
        count = 0
        active_ids = self._context.get('active_ids', [])
        if not active_ids:
            return res
        warn = any(
            (guia.invoice_state != 'none'\
             or guia.state != 'arquivada'\
             or guia.tipo not in ('remessa', 'transporte'))
            for guia in guia_obj.browse(active_ids))
        if warn:
            raise Warning(
                _('The waybill(s) are not in state draft or are '
                  'already invoiced or not type "Remessa" or "Transporte"'))
        return res

    @api.multi
    def open_invoice(self, invoice_type='out_invoice'):
        guia_obj = self.env['account.guia']
        context = dict(
            self._context,
            date_inv=self.invoice_date,
            type=invoice_type,
            group=self.group,
        )
        active_ids = self._context.get('active_ids', [])
        waybills = guia_obj.browse(active_ids)
        return waybills.with_context(context).action_invoice_onguia()


class WaybillSimplifiedInvoice(models.TransientModel):
    _name = "waybill.simplified.invoice"
    _inherit = "waybill.invoice"
    _description = "Account PT Simplified Invoice Waybill"

    @api.multi
    def open_simplified_invoice(self):
        return self.open_invoice('simplified_invoice')
