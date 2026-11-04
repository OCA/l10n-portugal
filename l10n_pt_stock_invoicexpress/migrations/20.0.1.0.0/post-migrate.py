# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    # Operation types already using InvoiceXpress get the provider selected
    cr.execute(
        """
        UPDATE stock_picking_type
           SET l10n_pt_doc_provider = 'invoicexpress'
         WHERE invoicexpress_doc_type IS NOT NULL
           AND invoicexpress_doc_type <> 'none'
        """
    )
