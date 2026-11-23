# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models
from odoo.exceptions import ValidationError


class L10nPtEstablishment(models.Model):
    _name = "l10n.pt.establishment"
    _description = "Establishment"
    _order = "company_id, name, id"
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete="restrict",
    )
    address_id = fields.Many2one(
        "res.partner",
        string="Address",
        required=True,
        check_company=True,
        ondelete="restrict",
    )
    ss_establishment_code = fields.Char(
        string="Social Security Establishment Code", copy=False
    )
    ru_local_unit_id = fields.Char(string="Relatório Único Local Unit ID", copy=False)
    principal_cae = fields.Char(string="Principal CAE")
    date_start = fields.Date(string="Opening Date")
    date_end = fields.Date(string="Closing Date")
    active = fields.Boolean(default=True)

    _check_dates = models.Constraint(
        "CHECK(date_end IS NULL OR date_start IS NULL OR date_end >= date_start)",
        "The closing date cannot be earlier than the opening date.",
    )

    def write(self, vals):
        if "company_id" in vals and self.filtered(
            lambda establishment: establishment.company_id.id != vals["company_id"]
        ):
            raise ValidationError(
                self.env._("An establishment cannot be moved to another company.")
            )
        return super().write(vals)
