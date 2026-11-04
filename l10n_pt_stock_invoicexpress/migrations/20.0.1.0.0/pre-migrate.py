# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo.tools.sql import column_exists, rename_column

_logger = logging.getLogger(__name__)

COLUMN_RENAMES = (
    ("invoicexpress_id", "l10n_pt_doc_id"),
    ("invoicexpress_number", "l10n_pt_doc_number"),
    ("invoicexpress_permalink", "l10n_pt_doc_permalink"),
    ("invoicexpress_doc_type", "l10n_pt_doc_type"),
)


def migrate(cr, version):
    for old, new in COLUMN_RENAMES:
        if column_exists(cr, "stock_picking", old):
            _logger.info("Renaming stock_picking.%s to %s", old, new)
            rename_column(cr, "stock_picking", old, new)
