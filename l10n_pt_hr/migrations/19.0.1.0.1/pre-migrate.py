# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

"""Rename ``l10n.pt.irct`` to ``l10n.pt.collective.contract``.

The model keeps its historical table (``_table = "l10n_pt_irct"``), so
only registry metadata is rewritten here — physical tables, record ids
and relationship columns are untouched. Field/view/action/access XML ids
keep their historical names; only the ``ir.model``/``ir.model.fields``
entries are moved to the canonical new names before ORM reflection.
"""


def migrate(cr, version):
    old = "l10n.pt.irct"
    new = "l10n.pt.collective.contract"
    old_table = "l10n_pt_irct"
    new_model_key = "l10n_pt_collective_contract"

    cr.execute("UPDATE ir_model SET model = %s WHERE model = %s", (new, old))
    cr.execute("UPDATE ir_model_fields SET model = %s WHERE model = %s", (new, old))
    cr.execute(
        "UPDATE ir_model_fields SET relation = %s WHERE relation = %s",
        (new, old),
    )
    cr.execute("UPDATE ir_model_data SET model = %s WHERE model = %s", (new, old))
    cr.execute(
        "UPDATE ir_model_data SET name = %s "
        "WHERE module = 'l10n_pt_hr' AND model = 'ir.model' AND name = %s",
        (f"model_{new_model_key}", f"model_{old_table}"),
    )
    cr.execute(
        "UPDATE ir_model_data SET name = %s || substr(name, %s) "
        "WHERE module = 'l10n_pt_hr' AND model = 'ir.model.fields' "
        "AND starts_with(name, %s)",
        (
            f"field_{new_model_key}__",
            len(f"field_{old_table}__") + 1,
            f"field_{old_table}__",
        ),
    )
    cr.execute("UPDATE ir_ui_view SET model = %s WHERE model = %s", (new, old))
    cr.execute(
        "UPDATE ir_act_window SET res_model = %s WHERE res_model = %s",
        (new, old),
    )
