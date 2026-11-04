# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    l10n_pt_doc_provider = fields.Selection(
        selection="_selection_l10n_pt_doc_provider",
        string="Legal Document Provider",
        help="Provider used to create legal transport documents"
        " for deliveries of this operation type.",
    )

    @api.model
    def _selection_l10n_pt_doc_provider(self):
        Provider = self.env["l10n_pt.invoice.provider"]
        return [
            (code, Provider._get_provider(code)._description)
            for code in Provider._provider_codes()
        ]
