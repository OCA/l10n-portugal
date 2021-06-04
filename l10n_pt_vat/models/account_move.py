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
    l10npt_vat_exempt_reason = fields.Many2one(
        "account.l10n_pt.vat.exempt.reason",
        string="VAT Exempt Reason",
        compute="_compute_l10npt_vat_exempt_reason",
        store=True,
        readonly=False,
    )

    @api.depends("journal_id", "company_id")
    def _compute_l10npt_vat_exempt_reason(self):
        for invoice in self.filtered(
            lambda x: x.country_code == "PT" and x.is_sale_document()
        ):
            invoice.l10npt_vat_exempt_reason = (
                invoice.journal_id.l10npt_vat_exempt_reason
            )

    @api.constrains("l10npt_vat_exempt_reason")
    def _constrain_l10npt_vat_exempt_reason(self):
        """
        VAT Exemption reason is required if an exempt tax is used
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
