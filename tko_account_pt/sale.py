# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 Thinkopen Solutions, Lda. All Rights Reserved
#    http://www.thinkopensolutions.com.
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
from openerp.tools.translate import _


class sale_order(osv.osv):
    _name = "sale.order"
    _inherit = "sale.order"

    _columns = {
        'hide_discounts': fields.boolean(
            "Hide Discounts", required=False,
            help="If True is visible in report."),
    }
    # FIX problem of multicompany.

    def onchange_company_id(self, cr, uid, ids, partner_id, company_id,
                            context=None):
        ret = {'value': {}}
        if not partner_id or not company_id:
            return ret
        warehouse_obj = self.pool.get('stock.warehouse')
        partner_obj = self.pool.get('res.partner')
        warehouse_ids = warehouse_obj.search(
            cr, uid, [('company_id', '=', company_id)], limit=1,
            context=context)
        if warehouse_ids:
            ret['value']['warehouse_id'] = warehouse_ids[0]
        partner = partner_obj.browse(cr, uid, partner_id)
        if partner.company_id and partner.company_id.id != company_id:
            raise osv.except_osv(
                _('Error!'),
                _('Company must be iqual to company of partner!'))
        return ret

    # FIX problem of multicompany.
    def onchange_partner_id(self, cr, uid, ids, part, context=None):
        ret = super(sale_order, self).onchange_partner_id(
            cr, uid, ids, part, context)
        if part:
            partner_obj = self.pool.get('res.partner')
            partner = partner_obj.browse(cr, uid, part, context=context)
            ret['value'].update({'partner_email': partner.email,
                                 'partner_mobile': partner.mobile,
                                 'partner_phone': partner.phone})
            if partner.company_id:
                ret['value']['company_id'] = partner.company_id.id
        else:
            ret['value'].update(
                {'partner_email': False, 'partner_mobile': False,
                 'partner_phone': False, 'company_id': False})
        return ret
