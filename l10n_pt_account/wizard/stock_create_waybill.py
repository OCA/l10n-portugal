# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./

from openerp import models, fields, api, _
import openerp.addons.decimal_precision as dp


class StockPickingWaybillLine(models.TransientModel):
    _name = "stock.picking.waybill.line"
    _rec_name = 'product_id'

    product_id = fields.Many2one(
        'product.product', string="Product",
        required=True, ondelete='CASCADE')
    product_qty = fields.Float(
        string="Quantity",
        digits_compute=dp.get_precision('Product UoM'),
        required=True)
    product_uom = fields.Many2one(
        'product.uom', string='Unit of Measure',
        required=True, ondelete='CASCADE')
    move_id = fields.Many2one(
        'stock.move', string="Move", ondelete='CASCADE')
    wizard_id = fields.Many2one(
        'stock.picking.waybill', string="Wizard", ondelete='CASCADE')
    cost = fields.Float("Cost", help="Unit Cost for this product line")


class StockPickingWaybill(models.TransientModel):
    _name = "stock.picking.waybill"
    _description = "Creating Waybill From Picking Wizard"

    type_waybill = fields.Selection([
        ("remessa", "Remessa"),
        ("transporte", "Transporte"),
        ("devolucao", "Devolução")
    ], string="Waybill Type", required=True, index=True, default='remessa')
    with_cost = fields.Boolean(
        string="With Cost?", default=True,
        help="If true the waybill will be created with product cost.")
    group = fields.boolean(string="Group by partner")

    @api.model
    def view_init(self, fields_list):
        res = super(StockPickingWaybill, self).view_init(
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

    @api.model
    def default_get(self, fields):
        res = super(StockPickingWaybill, self).default_get(fields)
        picking_ids = self._context.get('active_ids', [])
        if not picking_ids \
           or self._context.get('active_model') != 'stock.picking' \
           or len(picking_ids) != 1:
            # Partial Picking Processing may only
            # be done for one picking at a time
            return res
        [picking_id] = picking_ids
        picking_obj = self.env['stock.picking']
        picking = picking_obj.browse(picking_id)
        picking_code = picking.picking_type_id.code
        if picking_code == 'outgoing' and picking.name.find('-return') > 0:
            res.update(type_waybill='devolucao')
        if picking_code == 'outgoing' and picking.invoice_state == 'none'\
           and picking.name.find('-return') < 0:
            res.update(type_waybill='transporte')
        return res

    @api.model
    def _check_invoice_control_conflicts_with_waybill_type(self,
                                                           type_waybill,
                                                           pickings):
        waybill_obj = self.env['account.guia']
        any_not_invoiced = any(p.invoice_state == 'none' for p in pickings)
        if type_waybill != 'transporte' and any_not_invoiced:
            selection = waybill_obj.fields_get(
                ['tipo'])['tipo']['selection']
            waybill_type_label = dict(selection)[type_waybill]
            raise Warning(
                _('To create %s waybills, the invoice control '
                  'must not be "Not Applicable"') % waybill_type_label)

    @api.multi
    def create_waybill(self):
        waybill_ids = []
        action_model = False
        action = {}
        data_pool = self.env['ir.model.data']
        picking_obj = self.env['stock.picking']
        fields = ['date', 'type_waybill', 'with_cost', 'move_ids', 'group']
        active_ids = self._context.get('active_ids', [])
        context = dict(
            self._context,
            type_waybill=self.type_waybill,
            with_cost=self.with_cost,
            type_waybill=self.type_waybill
        )
        pickings = picking_obj.with_context(context).browse(active_ids)

        self._check_invoice_control_conflicts_with_waybill_type(
            type_waybill, pickings)

        res = pickings.action_waybill_create(self.group)
        waybill_ids += res.values()
        if not waybill_ids:
            raise Warning(_('No Waybills were created.'))
        # Get action for waybills
        if type_waybill == 'remessa':
            action_model, action_id = data_pool.get_object_reference(
                'l10n_pt_account', "action_account_guia_remessa_form")
        elif type_waybill == 'transporte':
            action_model, action_id = data_pool.get_object_reference(
                'l10n_pt_account', "action_account_guia_transporte_form")
        elif type_waybill == 'devolucao':
            action_model, action_id = data_pool.get_object_reference(
                'l10n_pt_account', "action_account_guia_devolucao_form")
        if action_model:
            action_pool = self.env[action_model]
            action = action_pool.browse(action_id).read()
            waybill_ids_str = ','.join(map(str, waybill_ids))
            action['domain'] = "[('id','in', [" + waybill_ids_str + "])]"
        return action


