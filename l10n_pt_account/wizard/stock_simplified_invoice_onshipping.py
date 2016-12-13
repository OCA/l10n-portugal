# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./
from openerp import models, fields, api, _
from openerp.exceptions import Warning


class StockSimplifiedOnshipping(models.TransientModel):
    _name = "stock.simplified.invoice.onshipping"
    _description = "Account PT Stock Simplified Invoice Onshipping"

    @api.model
    def _get_journal(self):
        res = self._get_journal_id()
        if res:
            return res[0][0]
        return False

    @api.model
    def _get_journal_id(self):
        model = self._context.get('active_model')
        if not model or 'stock.picking' not in model:
            return []

        model_pool = self.env[model]
        journal_obj = self.env['account.journal']
        res_ids = self._context.get('active_ids', [])
        vals = set()
        browse_picking = model_pool.browse(res_ids)

        for pick in browse_picking:
            if not pick.move_lines:
                continue
            src_usage = pick.move_lines[0].location_id.usage
            dest_usage = pick.move_lines[0].location_dest_id.usage
            type = pick.type
            if type == 'out' and dest_usage == 'supplier':
                journal_type = 'purchase_refund'
            elif type == 'out' and dest_usage == 'customer':
                journal_type = 'sale'
            elif type == 'in' and src_usage == 'supplier':
                journal_type = ('purchase',)
            elif type == 'in' and src_usage == 'customer':
                journal_type = 'sale_refund'
            else:
                journal_type = 'sale'

            journals = journal_obj.search([('type', '=', journal_type)])
            vals.update((j.id, j.name) for j in journals)
        if not vals:
            raise Warning(
                _('Either there are no moves linked to the picking or '
                  'Accounting Journals are misconfigured!'))
        return list(vals)

    journal_id = fields.Selection(
        _get_journal_id, string='Destination Journal', required=True,
        default=_get_journal)
    group = fields.Boolean(string="Group by partner")
    invoice_date = fields.Date(string='Invoiced date')

    @api.model
    def view_init(self, fields_list):
        res = super(StockSimplifiedOnshipping, self).view_init(
            fields_list)
        pick_obj = self.env['stock.picking']
        count = 0
        active_ids = self._context.get('active_ids', [])
        for pick in pick_obj.browse(active_ids):
            if pick.invoice_state != '2binvoiced'\
               or pick.waybill_state != 'none':
                count += 1
        if len(active_ids) == 1 and count:
            raise Warning( 
                _('This picking list does not require invoicing or '
                  'already created a waybill.'))
        if len(active_ids) == count:
            raise Warning( 
                _('None of these picking lists require invoicing or '
                  'already created a waybill.'))
        return res

    @api.multi
    def open_simplified(self):
        invoice_ids = []
        data_pool = self.env['ir.model.data']
        res = self.create_simplified_invoice()
        invoice_ids += res.values()
        action_model = False
        action = {}
        if not invoice_ids:
            raise Warning(_(
                'No Simplified Invoices were created.'))
        action_model, action_id = data_pool.get_object_reference(
            'l10n_pt_account', "action_simplified_invoice_tree")
        if action_model:
            action_pool = self.env[action_model]
            action = action_pool.browse(action_id).read()
            action['domain'] = str([('id', 'in', invoice_ids)])
        return action

    @api.multi
    def create_simplified_invoice(self):
        context = dict(self._context, date_inv=self.invoice_date)
        active_ids = self._context.get('active_ids', [])
        pickings = self.env['stock.picking'].browse(active_ids)
        return pickings.with_context(context).action_invoice_create(
            journal_id=self.journal_id,
            group=self.group,
            type='simplified_invoice',
        )
