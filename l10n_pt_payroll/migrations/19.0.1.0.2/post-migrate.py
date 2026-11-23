# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tools import sql


def migrate(cr, version):
    # payment_method_id replaces the short-lived l10n_pt_payment_method_id
    # column; copy stored assignments without touching the old column.
    if sql.column_exists(cr, "hr_version", "l10n_pt_payment_method_id"):
        cr.execute(
            """
            UPDATE hr_version
            SET payment_method_id = l10n_pt_payment_method_id
            WHERE payment_method_id IS NULL
            AND l10n_pt_payment_method_id IS NOT NULL
            """
        )
