# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo.tools.sql import column_exists, rename_column

_logger = logging.getLogger(__name__)

COLUMN_RENAMES = (
    ("invoicexpress_id", "l10n_pt_doc_id"),
    ("invoicexpress_permalink", "l10n_pt_doc_permalink"),
    ("invoicexpress_doc_type", "l10n_pt_doc_type"),
)


def migrate(cr, version):
    for old, new in COLUMN_RENAMES:
        if column_exists(cr, "account_move", old):
            _logger.info("Renaming account_move.%s to %s", old, new)
            rename_column(cr, "account_move", old, new)
