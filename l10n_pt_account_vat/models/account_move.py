# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import exceptions, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        # Zero-rate PT taxes must carry an exemption reason code,
        # also on lines mixing exempt and nonzero taxes.
        # Enforced at posting time instead of on the tax record,
        # to stay safe with legacy data.
        for invoice in self.filtered(
            lambda m: m.country_code == "PT" and m.is_sale_document()
        ):
            lines = invoice.invoice_line_ids.filtered(
                lambda x: x.display_type not in ["line_section", "line_note"]
            )
            missing_reason = lines.tax_ids.filtered(
                lambda t: (
                    t.country_code == "PT"
                    and not t.amount
                    and not t.l10n_pt_tax_exemption_reason
                )
            )
            if missing_reason:
                raise exceptions.ValidationError(
                    self.env._(
                        "Exempt taxes require an exemption reason: %(taxes)s",
                        taxes=", ".join(missing_reason.mapped("name")),
                    )
                )
        return super().action_post()
