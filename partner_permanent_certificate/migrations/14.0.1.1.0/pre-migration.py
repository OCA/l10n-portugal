from openupgradelib import openupgrade

field_renames = [
    (
        "res.partner",
        "res_partner",
        "perm_certificate_code",
        "l10n_pt_perm_certificate_code",
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, field_renames)
