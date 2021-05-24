# Copyright (C) 2021 Open Source Integrators

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    invoicexpress_account_name = fields.Char(string="InvoiceXpress Account Name")
    invoicexpress_api_key = fields.Char(string="InvoiceXpress Api Key")

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICPSudo = self.env["ir.config_parameter"].sudo()

        ICPSudo.set_param("invoicexpress.account_name", self.invoicexpress_account_name)
        ICPSudo.set_param("invoicexpress.api_key", self.invoicexpress_api_key)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICPSudo = self.env["ir.config_parameter"].sudo()

        res.update(
            {
                "invoicexpress_account_name": ICPSudo.get_param(
                    "invoicexpress.account_name", default=""
                ),
                "invoicexpress_api_key": ICPSudo.get_param(
                    "invoicexpress.api_key", default=""
                ),
            }
        )
        return res
