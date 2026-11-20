Keep the legacy `l10n_pt_vat` models and catalog data installable on
Odoo 20 so upgraded databases preserve their VAT adjustment norms,
exemption reasons and document links unchanged. The module provides
no views or business logic; the replacement features live in
`l10n_pt_account_vat` and `l10n_pt_account_invoice`, which have no
dependency on this module. It is not meant for new deployments and
can be uninstalled once the upgrade has been verified.
