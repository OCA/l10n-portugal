# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from calendar import isleap
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10nPtPublicHolidayRule(models.Model):
    _name = "l10n.pt.public.holiday.rule"
    _description = "Portuguese Public Holiday Rule"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    mandatory = fields.Boolean()
    rule_type = fields.Selection(
        [("fixed", "Fixed Date"), ("easter", "Relative to Easter")],
        required=True,
        default="fixed",
    )
    month = fields.Integer(default=1)
    day = fields.Integer(default=1)
    easter_offset = fields.Integer(string="Days from Easter Sunday")

    @api.constrains("rule_type", "month", "day", "easter_offset")
    def _check_rule_date(self):
        for rule in self:
            if rule.rule_type == "fixed":
                try:
                    date(2000, rule.month, rule.day)
                except ValueError as error:
                    raise ValidationError(
                        self.env._("Enter a valid month and day for a fixed holiday.")
                    ) from error
            elif not -70 <= rule.easter_offset <= 70:
                raise ValidationError(
                    self.env._("Enter an Easter offset between -70 and 70 days.")
                )

    def _date_in_year(self, year, easter_day):
        self.ensure_one()
        if self.rule_type == "easter":
            return easter_day + timedelta(days=self.easter_offset)
        if (self.month, self.day) == (2, 29) and not isleap(year):
            return False
        return date(year, self.month, self.day)
