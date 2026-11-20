# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.addons.l10n_pt_account_vat.hooks import preserve_legacy_vat


def migrate(cr, version):
    preserve_legacy_vat(cr)
    # Keep the moved model and fields when updating VAT without the invoice addon.
    cr.execute(
        """
        UPDATE ir_model_data SET noupdate = TRUE
         WHERE module = 'l10n_pt_account_vat'
           AND (
               (model = 'ir.model' AND name = 'model_account_vat_adjustment_norm')
               OR (model = 'ir.model.fields' AND (
                   starts_with(name, 'field_account_vat_adjustment_norm__')
                   OR name IN ('field_account_move__vat_adjustment_norm_id',
                               'field_account_move__vat_adjustment_norm_note')
               ))
               OR model = 'account.vat.adjustment_norm'
           )
        """
    )
