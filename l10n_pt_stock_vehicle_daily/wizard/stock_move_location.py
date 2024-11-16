# Copyright 2024 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockMoveLocationWizard(models.TransientModel):
    _inherit = "wiz.stock.move.location"

    @api.depends("origin_location_id", "picking_type_id")
    def _compute_destination_location_id(self):
        for wiz in self:
            # Copy the Origin Location to the Destination Location
            # If it is an Internal move and the Location has is a vehicle/has a Plate
            type_is_internal = wiz.picking_type_id.code == "internal"
            location_has_plate = bool(wiz.origin_location_id.l10n_pt_license_plate)
            if type_is_internal and location_has_plate:
                wiz.destination_location_id = wiz.origin_location_id

    @api.depends("origin_location_id")
    def _compute_l10n_pt_license_plate(self):
        for wiz in self:
            # Set the Default License Plate configured in the Location
            wiz.l10n_pt_license_plate = wiz.origin_location_id.l10n_pt_license_plate

    destination_location_id = fields.Many2one(
        # extend to add automatic calculation
        compute="_compute_destination_location_id",
        store=True,
        readonly=False,
    )

    l10n_pt_license_plate = fields.Char(
        string="License Plate",
        compute="_compute_l10n_pt_license_plate",
        store=True,
        readonly=False,
    )

    def _create_picking(self):
        # Extend to set License Plate
        picking = super()._create_picking()
        picking.write({"l10n_pt_license_plate": self.l10n_pt_license_plate})
        return picking
