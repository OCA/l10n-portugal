# VAT adjustment norms transition — spec

**Status:** in progress — the `l10n_pt_vat` shim plan below was superseded on
2026-11-20; see "Superseded decisions". **Date:** 2026-11-15 **Scope:**
`l10n_pt_account_vat` (LGPL, this repo); `l10n_pt_vat` is removed from the 20.0 tree. No
changes to `l10n_pt_hr`, `l10n_pt_payroll`, stock or InvoiceXpress modules. **Related:**
none yet — first spec in this module.

## Context

`l10n_pt_vat` is the legacy AGPL module. Its VAT adjustment norm feature (fields 40/41
of the VAT statement, Portaria nº 255/2013) and its document-level exemption reason are
being replaced:

- The norm catalog, the `account.move` selector and the archival fields move to the LGPL
  `l10n_pt_account_vat`, which already owns the PT tax data model mirroring
  `l10n_pt_certification`.
- The 20.0 tree ships `l10n_pt_account_vat`, `l10n_pt_account_invoice`
  and a data-only `l10n_pt_vat` that preserves the legacy schema and
  catalog during upgrade; the successors migrate independently.

AGPL code is never copied into the LGPL module: the norm model, views and data are newly
authored here.

## Spec

### Norm model and catalog

- New model `account.vat.adjustment_norm` ("VAT Adjustment Legal Basis"), ordered by
  `name, id`, with exactly:
  - `name` Char, required.
  - `active` Boolean, default True.
  - `note` Text, translate — the legal mention shown on the document.
  - `out_refunds` Boolean "Customer Credit Notes".
  - `in_refunds` Boolean "Vendor Credit Notes".
- The catalog is configurable: a fresh install ships no copied records and makes no
  statutory claims about defaults; administrators create the norms their company uses.
- Access: read for `account.group_account_invoice` and `account.group_account_readonly`,
  full CRUD for `account.group_account_manager` (`security/ir.access.csv`).
- Configuration UI: list and form under the Accounting configuration menu
  (`account.account_account_menu`), new XMLIDs owned by `l10n_pt_account_vat`.

### `account.move` fields

- `vat_adjustment_norm_id`: Many2one to the norm, `ondelete="restrict"`, `copy=False`,
  string "VAT Adjustment Legal Basis".
- `vat_adjustment_norm_note`: Text, related to `vat_adjustment_norm_id.note` (the legal
  text shown read-only).
- `l10n_pt_legacy_vat_exemption_code`: Char, `readonly`, `copy=False` — historical
  snapshot of the legacy document-level exemption code.
- No change to posting or tax behavior in this step.

### Document selector

- On the invoice form, right after `journal_div`, the norm field shows only when
  `country_code == 'PT'` and `move_type` is `out_refund` or `in_refund`, and is editable
  only in draft.
- Its domain keeps only norms flagged for the document direction: `out_refunds` for
  customer credit notes, `in_refunds` for vendor credit notes. A norm flagged for both
  directions is usable on both.
- The related note shows the selected norm's legal text; quick-create is disabled.
- Other move types never show the selector.

### Migration and preservation

- `l10n_pt_account_vat/hooks.py` gains two shared helpers:
  - `preserve_legacy_vat(cr)`: creates `l10n_pt_legacy_vat_exemption_code` when missing
    and backfills it from the legacy `l10npt_vat_exempt_reason` Many2one (code snapshot,
    NULL-safe, never overwrites); then transfers the `ir.model.data` rows of
    `account.vat.adjustment_norm` from module `l10n_pt_vat` to `l10n_pt_account_vat` —
    same `res_id`, notes and flags preserved, old names kept as `noupdate` aliases,
    insert idempotent.
  - `apply_legacy_tax_regions(env)`: maps legacy `account.tax.l10n_pt_fiscal_zone`
    values onto `account.tax.group.l10n_pt_tax_region`, preferring the current column
    and falling back to `l10n_pt_fiscal_zone_old`; only groups whose taxes agree on a
    single `PT-MA`/`PT-AC` zone are set — inferred Mainland defaults and conflicting
    zones are preserved, never guessed.
- `l10n_pt_account_vat` 20.0.1.1.0: `pre_init_hook` calls `preserve_legacy_vat(env.cr)`;
  `post_init_hook` keeps `_fill_tax_groups(env)` then `apply_legacy_tax_regions(env)`;
  new `migrations/20.0.1.1.0/` pre/post wrappers call the same helpers (pre with `cr`,
  post with `api.Environment(cr, SUPERUSER_ID, {})`).
- Old invoice taxes and journal values are never mutated; obsolete or unknown codes are
  never relabeled or converted.

### `l10n_pt_vat` shim — SUPERSEDED (see below)

The following section described an earlier plan kept for the record; it was rejected on
2026-11-20 in favour of retiring the module outright.

- Manifest: name suffix "(Deprecated)", compatibility-only summary, version 20.0.1.1.0,
  keeps the `l10n_pt_account_vat` dependency.
- `models/account_move.py` reduced to a single archival field:
  `l10npt_vat_exempt_reason` Many2one to `account.l10n_pt.vat.exempt.reason`,
  `readonly`, `copy=False`. All business logic (computes, `action_post` check) is
  removed; old source files may stay unimported.
- `account.journal.l10npt_vat_exempt_reason` becomes readonly archival.
- The exempt reason model, its ACL rows and `data/vat_exempt_reason.xml` stay so old
  readers and XMLIDs keep working; every other view and data loader leaves the manifest.
- The norm model import is removed (the model now belongs to `l10n_pt_account_vat`);
  norm ACL rows leave the shim's security file.
- Retired write/validation tests leave the test collection; a small compatibility test
  keeps covering the surviving archival contract.
- Technical note: because the old norm XMLIDs remain as aliases owned by the new module,
  an upgraded database must _upgrade_ the shim — never uninstall the old original
  version — until dependent modules migrate and a dedicated uninstall migration exists.

## Explicit non-goals

- No automatic archival flag guessing: nothing infers `out_refunds` / `in_refunds` or
  the archival code from old data heuristics.
- No automatic tax replacement: existing taxes, journal defaults and invoice lines are
  never rewritten.
- No statistical claims that the configurable catalog matches the official table —
  administrators own the contents.

## Deferred

- InvoiceXpress still needs to consume the legacy snapshot for historical invoices and
  derive new exemption codes from line taxes. Guides remain out of scope.

## Alternatives considered

- Keep norms in the AGPL module and mirror them into LGPL: rejected — duplicates the
  model and keeps the feature under the wrong license.
- Copy the old norm catalog into `l10n_pt_account_vat` data: rejected — duplicates
  records on upgrade and asserts statutory defaults the module does not guarantee.
- Drop the legacy `l10npt_vat_exempt_reason` column or convert codes: rejected —
  destroys user data and breaks old readers.
- Auto-derive archival flags from old `move_type` compute values: rejected — silent
  guessing on legal-basis data.

## Superseded decisions

### 2026-11-20 — `l10n_pt_vat` is retired, not shimmed

The earlier plan kept `l10n_pt_vat` installable on 20.0 as a deprecated compatibility
shim (archival Many2one fields, retained reason model/ACLs/data, reduced manifest). That
plan is **rejected**: the module is not ported to 20.0 at all — its source directory is
removed from this branch.

The compatibility layer lives in `l10n_pt_account_vat` instead:

- `account.move.l10n_pt_legacy_vat_exemption_code` ("Historical VAT Exemption Code")
  exposes the snapshot read-only on the invoice form; no legacy API field and no journal
  default remain in the registry.
- `preserve_legacy_vat(cr)` (pre-init hook and pre-migration wrapper) owns the raw
  snapshot backfill and the norm XMLID aliasing.
- `apply_legacy_tax_regions(env)` owns the legacy tax-region mapping.
- `migrations/20.0.1.1.0/retire_l10n_pt_vat.py` is an explicit `--pre-upgrade-scripts` step run before
  the base load/dependency graph (only with `-u`): it refuses to run unless
  `l10n_pt_vat` is absent from the addons paths, `l10n_pt_account_vat` is scheduled, and
  no incompatible dependent remains; then it deactivates the legacy views/menus and
  marks the module `uninstallable` — never uninstalling, so no data is deleted.
  **Superseded** by the migration-only stub below.
- The raw legacy columns and `account_l10n_pt_vat_exempt_reason` table stay in upgraded
  databases but are unsupported; only the invoice code is exposed, read-only.
- The shim plan also proposed legacy pre- and post-migration wrappers; none ship.

### 2026-11-20 — credit-note norms move to l10n_pt_account_invoice

The standalone invoice addon now owns the norm catalog, credit-note
selector and norm XMLID migration. VAT continues to own WIP-compatible
tax extensions, the archived exemption code, fiscal zones and legacy
module retirement. Neither addon depends on the other. Norm rows and
credit-note links remain intact if only the VAT addon is installed
during an upgrade. Installing the invoice addon later exposes the same
records and adds successor XMLID aliases. There is no change to
selector behavior, no new obligation on credit notes, and no SAF-T or
boxes 40/41 annex generation.

The norm model/catalog, `account.move` selector and norm XMLID
migration described in the sections above are superseded by this
decision and now live in `l10n_pt_account_invoice` (see its
`readme/SPECS.md`); they are kept here as history.

### 2026-11-20 — `l10n_pt_vat` returns as a migration-only stub

The explicit `--pre-upgrade-scripts` retirement step
(`migrations/20.0.1.1.0/retire_l10n_pt_vat.py`, removed) is superseded:
`l10n_pt_vat` ships again on 20.0 as a stub with no models, data or
menus, depending on `l10n_pt_account_vat`. A normal
`-u l10n_pt_vat` upgrade now performs the retirement: the stub's
pre-migration marks every legacy `ir.model.data` row `noupdate`,
deactivates the old views, menus and access rules, and snapshots the
exemption codes. The post-migration maps the fiscal regions. Odoo's
end-of-upgrade cleanup preserves the legacy metadata and data instead
of pruning it.

- Updating the stub deactivates the obsolete views, menus and access
  rules and prevents cleanup of the legacy metadata and data; it does
  not install `l10n_pt_account_invoice`.
- The stub could not be uninstalled while it still owned legacy
  XMLIDs (its uninstall hook refused); already-retired databases do
  not need it installed. **Superseded** by the uninstall handover
  below.
- The old Python field/model API is deliberately not restored; every
  record id is left untouched and no tax is rewritten.

### 2026-11-20 — the stub hands over XMLID ownership on uninstall

The uninstall refusal is superseded: once the migration is complete
the stub can be uninstalled. Odoo calls `uninstall_hook` before it
treats the module's still-owned records and columns as stub data, so
the hook first moves every legacy `ir.model.data` row it owns —
except the obsolete view XMLIDs, which stay with the stub and are
removed with it — into the `l10n_pt_vat_archive` namespace with
`noupdate`. Record and column ids never change; the archived
namespace simply keeps Odoo from pruning the preserved metadata and
data.

- No successor addon depends on the stub: `l10n_pt_account_vat`
  depends on `account`/`l10n_pt`, `l10n_pt_account_invoice` on
  `account`/`l10n_pt`, and only the stub depends on
  `l10n_pt_account_vat`, so removing the stub breaks nothing.
- `l10n_pt_account_invoice`'s XMLID aliasing also reads the
  `l10n_pt_vat_archive` namespace, so installing it after the stub
  has been uninstalled still exposes the original norms.

### 2026-11-20 — `l10n_pt_vat` keeps its schema; successors migrate independently

The migration-only stub and the `l10n_pt_vat_archive` uninstall
handover are superseded: `l10n_pt_vat` ships its original models,
catalog data, translations and ACLs unchanged — no hooks, no
migration scripts, no views and no business logic — so a normal
module update preserves the legacy schema, catalog rows, customized
notes/flags/records and move links exactly as stored. The legacy
module has no dependency on either successor, and neither successor
depends on it.

The supported order is explicit: update `l10n_pt_vat` first after
the core upgrade, then install or update `l10n_pt_account_vat` —
which snapshots the historical exemption codes and maps the fiscal
regions — and install `l10n_pt_account_invoice`, which copies the
norm catalog into its own model and table and rewrites the
credit-note links. Uninstalling `l10n_pt_vat` is optional and only
after verifying those copies; Odoo's normal uninstall may then
discard the original duplicates without affecting successor
behavior. No historical invoice-line tax is rewritten at any step.

`l10n_pt_account_invoice` supports initial installation only;
databases that already run a preview build of that addon are not
covered by a release upgrade (see its `readme/SPECS.md`).

### 2026-11-20 — migration wrappers consolidated at the first release version

The first release is `20.0.1.0.0`; the preview migration folders
`20.0.1.1.0`, `20.0.1.2.0` and `20.0.1.3.0` are consolidated into a
single `20.0.1.0.0` folder. Odoo runs `pre-*`/`post-*` scripts only
for folder versions greater than the installed version and up to the
manifest version, so the consolidated pre-migrate also carries the
norm-metadata `noupdate` protection that previously lived in the
1.2.0 script, and post-migrate keeps the fiscal-region mapping.

A database that installed a preview build with a higher version is
not downgraded and does not re-run the scripts. Fresh installations
are unchanged: `pre_init_hook` and `post_init_hook` still perform
the snapshot and region mapping.

## Tasks

- [x] Spec this transition.
- [x] `l10n_pt_account_vat`: norm model, move fields, ACL, views, manifest bump + hooks,
      migration wrappers, retirement script.
- [x] `l10n_pt_vat`: migration-only stub replaces the explicit retirement
      script (shim and removal-only plans superseded).
- [x] readme fragments; INSTALL.md upgrade path; regenerate README.rst / index.html.
- [x] Tests: norm selector story in `l10n_pt_account_vat`.
- [x] Verify on a fresh disposable database: install `l10n_pt_account_vat`, run module
      tests, pre-commit. Synthetic legacy-schema fixtures and the clean installation
      passed; a real upgraded database has not been exercised.
- [x] Verify `-u l10n_pt_vat` on an Odoo 20 database seeded with legacy data:
      VAT auto-installs, the old UI and permissions are disabled, and a later
      invoice addon installation exposes the original norm and credit-note link.
- [ ] Run a complete upgrade from a copy of a real 19.0 database.
