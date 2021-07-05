# Copyright (C) 2014 Sossia, Lda. (<http://www.sossia.pt>)
# Copyright (C) 2021 Open SOurce Integrators (<http://www.opensourceintegrators.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, exceptions, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    vat_adjustment_norm_id = fields.Many2one(
        "account.vat.adjustment_norm",
        string="VAT Adjustment Norm",
        ondelete="restrict",
        help="Fields 40/41 of the VAT Statement",
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

    @api.depends("country_code", "move_type", "invoice_line_ids.tax_ids")
    def _compute_l10npt_has_tax_exempt_lines(self):
        for invoice in self:
            invoice.l10npt_has_tax_exempt_lines = (
                invoice.country_code == "PT"
                and invoice.is_sale_document()
                and invoice.invoice_line_ids.filtered(
                    lambda x: not x.tax_ids.filtered("amount")
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
        for invoice in self.filtered(
            lambda x: x.country_code == "PT" and x.is_sale_document()
        ):
            exempt_lines = invoice.invoice_line_ids.filtered(
                lambda x: not x.tax_ids.filtered("amount")
            )
            if exempt_lines and not invoice.l10npt_vat_exempt_reason:
                raise exceptions.ValidationError(
                    _("A tax exemption reason must be provided.")
                )
        return super().action_post()
