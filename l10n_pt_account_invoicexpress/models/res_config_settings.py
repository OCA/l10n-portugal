# Copyright (C) 2021 Open Source Integrators

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    invoicexpress_account_name = fields.Char(
        related="company_id.invoicexpress_account_name",
        readonly=False,
        default=lambda s: s.env["ir.config_parameter"]
        .sudo()
        .get_param("invoicexpress.account_name", default=""),
    )
    invoicexpress_api_key = fields.Char(
        related="company_id.invoicexpress_api_key",
        readonly=False,
        default=lambda s: s.env["ir.config_parameter"]
        .sudo()
        .get_param("invoicexpress.api_key", default=""),
    )
    invoicexpress_template_id = fields.Many2one(
        related="company_id.invoicexpress_template_id", readonly=False
    )
