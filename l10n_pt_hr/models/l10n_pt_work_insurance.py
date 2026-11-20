# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class L10nPtWorkInsurance(models.Model):
    _name = "l10n.pt.work.insurance"
    _description = "Work Accident Insurance (SAT)"
    _order = "insurer_id, policy_number"
    _rec_name = "display_name"

    insurer_id = fields.Many2one(
        "res.partner",
        string="Insurer",
        required=True,
        help="Insurance company issuing the policy (seguradora).",
    )
    policy_number = fields.Char(required=True)
    date_start = fields.Date(string="Coverage Start")
    date_end = fields.Date(string="Coverage End")
    rate = fields.Float(
        string="Premium Rate (%)",
        digits=(16, 4),
        help="Work accident insurance (SAT) premium rate applied to "
        "the Social Security contribution base; varies by risk "
        "class (CAE) and insurer.",
    )
    active = fields.Boolean(default=True)

    @api.depends("insurer_id", "policy_number")
    def _compute_display_name(self):
        for record in self:
            record.display_name = (
                f"{record.insurer_id.name or ''} - {record.policy_number or ''}"
            ).strip(" -")
