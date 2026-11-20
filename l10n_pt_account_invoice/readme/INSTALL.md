**Fresh installation**

Install this addon normally. It does not require `l10n_pt_vat` or
`l10n_pt_account_vat`. The standard legal bases are loaded automatically. You can add or
customize entries as described in Usage.

**Upgrading an existing database**

If you need to keep legacy adjustment norms, install this addon
after updating `l10n_pt_vat` and before uninstalling it. The install
hook matches standard norms by XML ID, preserves legacy
values, and copies custom norms and their credit-note links. If there
is no legacy data, the standard catalog is available without migration.
