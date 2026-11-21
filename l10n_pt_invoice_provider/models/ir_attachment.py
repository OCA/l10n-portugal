# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    l10n_pt_doc_pdf_provider = fields.Char(
        string="Legal Document PDF Provider", readonly=True, copy=False
    )
