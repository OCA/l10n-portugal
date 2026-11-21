# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, exceptions, fields, models


class L10nPtInvoiceProviderRecord(models.Model):
    _name = "l10n_pt.invoice.provider.record"
    _description = "Legal Document Provider Registration"
    _order = "name, id"

    name = fields.Char(required=True)
    code = fields.Char(required=True, readonly=True, copy=False)
    adapter_installed = fields.Boolean(
        compute="_compute_adapter_installed", search="_search_adapter_installed"
    )
    _unique_code = models.Constraint(
        "UNIQUE(code)", "A legal document provider code must be unique."
    )

    @api.model
    def _register_provider(self, code):
        implementation = self.env["l10n_pt.invoice.provider"]._get_provider(code)
        if implementation is None:
            raise exceptions.UserError(
                self.env._(
                    "The legal document provider %(code)s is not installed.", code=code
                )
            )
        records = self.sudo()
        return records.search([("code", "=", code)], limit=1) or records.create(
            {"code": code, "name": implementation._description}
        )

    def _compute_adapter_installed(self):
        codes = set(self.env["l10n_pt.invoice.provider"]._provider_codes())
        for record in self:
            record.adapter_installed = record.code in codes

    @api.model
    def _search_adapter_installed(self, operator, value):
        # Odoo normalizes boolean search to in/not in; do not persist availability.
        if operator not in ("in", "not in"):
            return NotImplemented
        if len(set(value)) != 1:
            return (
                [("id", "!=", False)]
                if bool(value) == (operator == "in")
                else [("id", "=", False)]
            )
        positive = (True in value) == (operator == "in")
        return [
            (
                "code",
                "in" if positive else "not in",
                self.env["l10n_pt.invoice.provider"]._provider_codes(),
            )
        ]

    def write(self, vals):
        if "code" in vals and any(record.code != vals["code"] for record in self):
            raise exceptions.UserError(
                self.env._("The legal document provider code cannot be changed.")
            )
        return super().write(vals)
