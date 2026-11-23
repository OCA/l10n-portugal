# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import math

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10nPtCollectiveContract(models.Model):
    _name = "l10n.pt.collective.contract"
    # Keep the historical table so installed records and foreign keys
    # survive the model rename.
    _table = "l10n_pt_irct"
    _description = "Collective Contract"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        help="Official reference of the agreement, e.g. the BTE publication "
        "number or CCT code."
    )
    l10n_pt_full_time_hours = fields.Float(
        string="Full-Time Reference Hours",
        digits=(16, 2),
        help="Weekly hours of a full-time contract under this agreement; "
        "0 means not configured.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    @api.constrains("l10n_pt_full_time_hours")
    def _check_l10n_pt_full_time_hours(self):
        for irct in self:
            hours = irct.l10n_pt_full_time_hours
            if hours is None:
                continue
            if not math.isfinite(hours) or hours < 0:
                raise ValidationError(
                    self.env._(
                        "The full-time reference hours must be zero or a "
                        "positive finite number."
                    )
                )
