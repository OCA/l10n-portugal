# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class EasyPayPaymentMethod(models.Model):
    _name = "easypay.payment.method"
    _description = "EasyPay Payment Method"

    name = fields.Char(
        string="Method Name",
        required=True,
        translate=True,
    )
    code = fields.Char(
        string="Method Code",
        required=True,
        help="Internal code used by EasyPay API",
    )
