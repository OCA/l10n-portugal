# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT id FROM res_company WHERE active = true")
    company_ids = [row[0] for row in cr.fetchall()]
    if not company_ids:
        _logger.info("No active companies found; nothing to migrate")
        return

    _logger.info(
        "Populating empty invoicexpress_code entries from invoicexpress_id "
        "for active companies %s",
        company_ids,
    )

    # Partners restricted to a single company: set the code for that company only
    # when it does not already have a value there.
    cr.execute(
        """
        UPDATE res_partner
        SET invoicexpress_code =
            COALESCE(invoicexpress_code, '{}'::jsonb)
            || jsonb_build_object(company_id::text, invoicexpress_id)
        WHERE invoicexpress_id IS NOT NULL
          AND invoicexpress_id != ''
          AND company_id IS NOT NULL
          AND (
              invoicexpress_code IS NULL
              OR NOT (invoicexpress_code ? company_id::text)
          )
        """
    )
    migrated = cr.rowcount

    if len(company_ids) == 1:
        company_id = company_ids[0]
        cr.execute(
            """
            UPDATE res_partner
            SET invoicexpress_code =
                COALESCE(invoicexpress_code, '{}'::jsonb)
                || jsonb_build_object(%s::text, invoicexpress_id)
            WHERE invoicexpress_id IS NOT NULL
              AND invoicexpress_id != ''
              AND company_id IS NULL
              AND (
                  invoicexpress_code IS NULL
                  OR NOT (invoicexpress_code ? %s)
              )
            """,
            (company_id, str(company_id)),
        )
    else:
        # Shared partners: set the code for every active company that does not
        # already have one, preserving any existing per-company values.
        cr.execute(
            """
            UPDATE res_partner rp
            SET invoicexpress_code =
                COALESCE(rp.invoicexpress_code, '{}'::jsonb) || sub.code_obj
            FROM (
                SELECT rp2.id,
                       jsonb_object_agg(c.id::text, rp2.invoicexpress_id) AS code_obj
                FROM res_partner rp2
                CROSS JOIN res_company c
                WHERE rp2.invoicexpress_id IS NOT NULL
                  AND rp2.invoicexpress_id != ''
                  AND rp2.company_id IS NULL
                  AND c.active = true
                  AND (
                      rp2.invoicexpress_code IS NULL
                      OR NOT (rp2.invoicexpress_code ? c.id::text)
                  )
                GROUP BY rp2.id
            ) sub
            WHERE rp.id = sub.id
            """
        )

    migrated += cr.rowcount
    _logger.info(
        "Migrated %d partner(s) from invoicexpress_id to invoicexpress_code",
        migrated,
    )
