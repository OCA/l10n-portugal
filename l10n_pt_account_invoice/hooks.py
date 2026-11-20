# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tools.sql import column_exists, table_exists


def post_init_hook(env):
    cr = env.cr
    if not table_exists(cr, "account_vat_adjustment_norm"):
        return

    # Match seeded records before allocating IDs for custom legacy norms.
    cr.execute(
        """
        CREATE TEMP TABLE l10n_pt_invoice_norm_xmlids ON COMMIT DROP AS
        SELECT DISTINCT ON (xmlid.name) xmlid.name, xmlid.res_id AS legacy_id
          FROM ir_model_data AS xmlid
          JOIN account_vat_adjustment_norm AS norm ON norm.id = xmlid.res_id
         WHERE xmlid.model = 'account.vat.adjustment_norm'
           AND xmlid.module IN (
               'l10n_pt_vat', 'l10n_pt_vat_archive', 'l10n_pt_account_vat'
           )
      ORDER BY xmlid.name,
               CASE xmlid.module
                   WHEN 'l10n_pt_vat' THEN 0
                   WHEN 'l10n_pt_vat_archive' THEN 1
                   ELSE 2
               END
    """
    )
    cr.execute(
        """
        CREATE TEMP TABLE l10n_pt_invoice_norm_map ON COMMIT DROP AS
        WITH seeded AS (
            SELECT DISTINCT ON (legacy.legacy_id) legacy.legacy_id,
                   xmlid.res_id AS norm_id
              FROM l10n_pt_invoice_norm_xmlids AS legacy
              JOIN ir_model_data AS xmlid ON xmlid.name = legacy.name
              JOIN l10n_pt_vat_adjustment_norm AS norm ON norm.id = xmlid.res_id
             WHERE xmlid.module = 'l10n_pt_account_invoice'
               AND xmlid.model = 'l10n.pt.vat.adjustment.norm'
          ORDER BY legacy.legacy_id, xmlid.name
        )
        SELECT legacy.id AS legacy_id,
               COALESCE(seeded.norm_id, nextval(pg_get_serial_sequence(
                   'l10n_pt_vat_adjustment_norm', 'id'
               ))) AS norm_id
          FROM account_vat_adjustment_norm AS legacy
     LEFT JOIN seeded ON seeded.legacy_id = legacy.id
    """
    )
    cr.execute(
        """
        INSERT INTO l10n_pt_vat_adjustment_norm
                    (id, name, note, active, out_refunds, in_refunds)
             SELECT mapping.norm_id, legacy.name, legacy.note, legacy.active,
                    legacy.out_refunds, legacy.in_refunds
               FROM l10n_pt_invoice_norm_map AS mapping
               JOIN account_vat_adjustment_norm AS legacy
                 ON legacy.id = mapping.legacy_id
        ON CONFLICT (id) DO UPDATE
                SET name = EXCLUDED.name, note = EXCLUDED.note,
                    active = EXCLUDED.active, out_refunds = EXCLUDED.out_refunds,
                    in_refunds = EXCLUDED.in_refunds
    """
    )
    if column_exists(cr, "account_move", "vat_adjustment_norm_id"):
        cr.execute(
            """
            UPDATE account_move AS move
               SET l10n_pt_vat_adjustment_norm_id = mapping.norm_id
              FROM l10n_pt_invoice_norm_map AS mapping
             WHERE move.vat_adjustment_norm_id = mapping.legacy_id
               AND move.l10n_pt_vat_adjustment_norm_id IS NULL
            """
        )
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
             SELECT 'l10n_pt_account_invoice', xmlid.name,
                    'l10n.pt.vat.adjustment.norm', mapping.norm_id, TRUE
               FROM l10n_pt_invoice_norm_xmlids AS xmlid
               JOIN l10n_pt_invoice_norm_map AS mapping
                 ON mapping.legacy_id = xmlid.legacy_id
        ON CONFLICT (module, name) DO NOTHING
    """
    )
