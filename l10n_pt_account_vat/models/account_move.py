# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import exceptions, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        # PT requirement: a reason must be given whenever tax is not
        # charged. The tax itself requires one, but a tax stored before
        # that rule may still lack it; this catches those at posting.
        for invoice in self.filtered(
            lambda m: m.country_code == "PT" and m.is_sale_document()
        ):
            lines = invoice.invoice_line_ids.filtered(
                lambda x: x.display_type not in ["line_section", "line_note"]
            )
            missing_reason = lines.tax_ids.filtered(
                lambda t: t._l10n_pt_lacks_exemption_reason()
            )
            if missing_reason:
                raise exceptions.ValidationError(
                    self.env._(
                        "A tax that charges nothing needs a VAT exemption "
                        "reason: set one on %(taxes)s.",
                        taxes=", ".join(missing_reason.mapped("name")),
                    )
                )
        return super().action_post()
