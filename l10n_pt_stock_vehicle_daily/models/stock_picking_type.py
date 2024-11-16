# Copyright 2024 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    def action_move_location(self):
        action = super().action_move_location()
        # The Vehicle Locatin needs to be selected,
        # So by default enable editing the location field
        if self.code == "internal":
            action["context"]["default_edit_locations"] = True
        return action
