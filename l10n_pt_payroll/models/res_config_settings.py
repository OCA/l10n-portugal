# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_pt_full_time_hours = fields.Float(
        related="company_id.l10n_pt_full_time_hours",
        readonly=False,
    )
