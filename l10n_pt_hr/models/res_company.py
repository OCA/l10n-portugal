# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import math

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_pt_full_time_hours = fields.Float(
        string="Default Full-Time Hours",
        digits=(16, 2),
        default=40.0,
        required=True,
        help="Weekly hours used as the full-time reference for Portuguese "
        "contracts when the collective contract does not set one.",
    )
    l10n_pt_default_establishment_id = fields.Many2one(
        "l10n.pt.establishment",
        string="Default Establishment",
        ondelete="restrict",
        check_company=True,
        help="Establishment pre-assigned to new employees of this company; "
        "existing assignments are not changed.",
    )

    @api.constrains("l10n_pt_full_time_hours")
    def _check_l10n_pt_full_time_hours(self):
        for company in self:
            hours = company.l10n_pt_full_time_hours
            if not math.isfinite(hours) or hours <= 0:
                raise ValidationError(
                    self.env._("The default full-time hours must be a positive number.")
                )

    @api.constrains("l10n_pt_default_establishment_id")
    def _check_l10n_pt_default_establishment(self):
        self._check_company(["l10n_pt_default_establishment_id"])
