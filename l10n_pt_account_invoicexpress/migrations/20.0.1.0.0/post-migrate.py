# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    # Journals already using InvoiceXpress get the provider selected,
    # without replacing a provider already selected on the journal.
    cr.execute(
        """
        UPDATE account_journal
           SET l10n_pt_doc_provider = 'invoicexpress'
         WHERE l10n_pt_doc_provider IS NULL
           AND type = 'sale'
           AND invoicexpress_doc_type IS NOT NULL
           AND invoicexpress_doc_type <> 'none'
    """
    )
    cr.execute(
        """
        UPDATE account_move AS move
           SET l10n_pt_doc_provider = 'invoicexpress'
          FROM account_journal AS journal
         WHERE move.journal_id = journal.id
           AND move.move_type IN ('out_invoice', 'out_refund')
           AND move.l10n_pt_doc_provider IS NULL
           AND (journal.l10n_pt_doc_provider = 'invoicexpress'
                OR (move.l10n_pt_doc_id IS NOT NULL
                    AND journal.l10n_pt_doc_provider IS NULL))
    """
    )
    cr.execute(
        """
        UPDATE account_move
           SET l10n_pt_doc_number = name
         WHERE l10n_pt_doc_provider = 'invoicexpress'
           AND l10n_pt_doc_id IS NOT NULL
           AND l10n_pt_doc_number IS NULL
           AND state = 'posted'
           AND name <> '/'
        """
    )
