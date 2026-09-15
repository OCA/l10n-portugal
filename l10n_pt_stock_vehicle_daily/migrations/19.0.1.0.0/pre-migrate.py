# Copyright 2024 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """Rename l10n_pt_license_plate to license_plate."""
    # Rename field in stock.location
    openupgrade.rename_fields(
        env,
        [
            (
                "stock.location",
                "stock_location",
                "l10n_pt_license_plate",
                "license_plate",
            ),
        ],
    )
    # Rename field in stock.picking
    openupgrade.rename_fields(
        env,
        [
            (
                "stock.picking",
                "stock_picking",
                "l10n_pt_license_plate",
                "license_plate",
            ),
        ],
    )
