# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, exceptions, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    is_l10npt_vat_enabled = fields.Boolean(compute="_compute_is_l10npt_vat_enabled")
    vat_adjustment_norm_id = fields.Many2one(
        "account.vat.adjustment_norm",
        string="VAT Adjustment Norm",
        ondelete="restrict",
        help="Fields 40/41 of the VAT Statement",
    )
    vat_adjustment_norm_note = fields.Text(
        related="vat_adjustment_norm_id.note",
        string="VAT Adjustment Norm Details",
        readonly=True,
    )
    l10npt_has_tax_exempt_lines = fields.Boolean(
        compute="_compute_l10npt_has_tax_exempt_lines"
    )
    l10npt_vat_exempt_reason = fields.Many2one(
        "account.l10n_pt.vat.exempt.reason",
        string="VAT Exempt Reason",
        compute="_compute_l10npt_vat_exempt_reason",
        store=True,
        readonly=False,
    )

    def _compute_is_l10npt_vat_enabled(self):
        for invoice in self:
            invoice.is_l10npt_vat_enabled = (
                invoice.country_code == "PT" and invoice.is_sale_document()
            )

    @api.depends("country_code", "move_type", "invoice_line_ids")
    def _compute_l10npt_has_tax_exempt_lines(self):
        for invoice in self:
            invoice.l10npt_has_tax_exempt_lines = bool(
                invoice.country_code == "PT"
                and invoice.is_sale_document()
                and invoice.invoice_line_ids.filtered(
                    lambda x: not x.display_type and not x.tax_ids.filtered("amount")
                )
            )

    @api.depends(
        "l10npt_has_tax_exempt_lines", "journal_id", "company_id", "amount_total"
    )
    def _compute_l10npt_vat_exempt_reason(self):
        for invoice in self:
            if (
                invoice.l10npt_has_tax_exempt_lines
                and not invoice.l10npt_vat_exempt_reason
            ):
                invoice.l10npt_vat_exempt_reason = (
                    invoice.journal_id.l10npt_vat_exempt_reason
                )

    def action_post(self):
        """
        VAT Exemption reason is required if there are lines without tax
        """
        for invoice in self.filtered("is_l10npt_vat_enabled"):
            lines = invoice.invoice_line_ids.filtered(
                lambda x: x.display_type not in ["line_section", "line_note"]
            )
            exempt_lines = lines.filtered(lambda x: not x.tax_ids.filtered("amount"))
            if exempt_lines and not invoice.l10npt_vat_exempt_reason:
                raise exceptions.ValidationError(
                    self.env._("A tax exemption reason must be provided.")
                )
            # Zero-rate PT taxes must carry an exemption reason code,
            # also on lines mixing exempt and nonzero taxes.
            # Enforced at posting time instead of on the tax record,
            # to stay safe with legacy data.
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
