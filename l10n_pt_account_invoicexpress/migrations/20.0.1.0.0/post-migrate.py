# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api
from odoo.tools import SQL
from odoo.tools.sql import column_exists


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    provider_id = (
        env["l10n_pt.invoice.provider.record"]._register_provider("invoicexpress").id
    )
    # Journals already using InvoiceXpress get the provider selected,
    # without replacing a provider already selected on the journal.
    cr.execute(
        """
        UPDATE account_journal
           SET l10n_pt_doc_provider_id = %s
         WHERE l10n_pt_doc_provider_id IS NULL
           AND type = 'sale'
           AND invoicexpress_doc_type IS NOT NULL
           AND invoicexpress_doc_type <> 'none'
    """,
        (provider_id,),
    )
    for field_name in (
        "invoicexpress_account_name",
        "invoicexpress_api_key",
        "invoicexpress_template_id",
    ):
        if not column_exists(cr, "res_company", field_name):
            continue
        column = SQL.identifier(field_name)
        cr.execute(
            SQL(
                """
                UPDATE account_journal AS journal
                   SET %s = company.%s
                  FROM res_company AS company
                 WHERE company.id = journal.company_id
                   AND journal.%s IS NULL
                   AND company.%s IS NOT NULL
                   AND (journal.l10n_pt_doc_provider_id = %s
                        OR EXISTS (
                            SELECT 1 FROM account_move AS move
                             WHERE move.journal_id = journal.id
                               AND move.move_type IN ('out_invoice', 'out_refund')
                               AND move.l10n_pt_doc_id IS NOT NULL
                               AND (move.l10n_pt_doc_provider_id IS NULL
                                    OR move.l10n_pt_doc_provider_id = %s)
                        ))
                """,
                column,
                column,
                column,
                column,
                provider_id,
                provider_id,
            )
        )
    cr.execute(
        """
        UPDATE account_move AS move
           SET l10n_pt_doc_provider_id = %s
          FROM account_journal AS journal
         WHERE move.journal_id = journal.id
           AND move.move_type IN ('out_invoice', 'out_refund')
           AND move.l10n_pt_doc_provider_id IS NULL
           AND (move.l10n_pt_doc_id IS NOT NULL
                OR (move.state = 'draft'
                    AND journal.l10n_pt_doc_provider_id = %s))
    """,
        (provider_id, provider_id),
    )
    # Existing drafts do not go through the framework's creation defaults.
    cr.execute(
        """
        UPDATE account_move AS move
           SET l10n_pt_doc_type = CASE
               WHEN move.move_type = 'out_refund' THEN 'credit_note'
               ELSE journal.invoicexpress_doc_type
           END
          FROM account_journal AS journal
         WHERE move.journal_id = journal.id
           AND move.move_type IN ('out_invoice', 'out_refund')
           AND move.state = 'draft'
           AND move.l10n_pt_doc_id IS NULL
           AND move.l10n_pt_doc_provider_id = %s
           AND move.l10n_pt_doc_type IS NULL
           AND journal.l10n_pt_doc_provider_id = %s
           AND journal.invoicexpress_doc_type IS NOT NULL
           AND journal.invoicexpress_doc_type <> 'none'
        """,
        (provider_id, provider_id),
    )
    cr.execute(
        """
        UPDATE account_move
           SET l10n_pt_doc_number = name
         WHERE l10n_pt_doc_provider_id = %s
           AND l10n_pt_doc_id IS NOT NULL
           AND l10n_pt_doc_number IS NULL
           AND state = 'posted'
           AND name <> '/'
        """,
        (provider_id,),
    )
