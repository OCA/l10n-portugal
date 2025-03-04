# Copyright 2024 Open Source Integrators
# Copyright 2025 NuoBiT Solutions - Deniz Gallo <dgallo@nuobit.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    l10n_pt_license_plate = fields.Char(
        string="License Plate",
        compute="_compute_l10n_pt_license_plate",
        store=True,
        readonly=False,
    )

    @api.depends("location_id")
    def _compute_l10n_pt_license_plate(self):
        for picking in self:
            picking.l10n_pt_license_plate = picking.location_id.l10n_pt_license_plate
