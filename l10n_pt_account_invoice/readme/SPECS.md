# VAT adjustment norms in `l10n_pt_account_invoice` — spec

**Status:** in progress
**Date:** 2026-11-20
**Scope:** `l10n_pt_account_invoice` (LGPL-3, this repo). Splits the
credit-note norm feature out of `l10n_pt_account_vat`; see that
module's `readme/SPECS.md` for the shared transition record.
**Related:** `l10n_pt_account_vat` — sibling addon, no dependency in
either direction.

## Context

The VAT adjustment norm catalog, the credit-note selector and the
norm XMLID preservation were implemented inside `l10n_pt_account_vat`
at 20.0.1.1.0. The user approved splitting them into a standalone,
optional invoice addon so databases that only need the tax extensions
are not forced to carry the invoicing feature.

## Spec

### Ownership

- This addon owns: `account.vat.adjustment_norm`, the norm ACLs and
  configuration UI, the `account.move` norm fields and selector view,
  and the successor XMLID aliasing for norm records.
- `l10n_pt_account_vat` keeps: the WIP tax fields and checks, the
  historical exemption code snapshot and fiscal-region migration;
  `l10n_pt_vat` is retired during upgrade by its migration-only stub
  using the shared VAT hooks (see that module's `readme/SPECS.md`).
- Neither addon depends on the other. `l10n_pt_account_invoice`
  depends only on `account` and `l10n_pt`.

### Preservation

- Norm rows, notes, direction flags and credit-note links must remain
  intact whether this addon is installed during the upgrade or later.
- `pre_init_hook` links `l10n_pt_account_invoice.*` successor XMLIDs
  to the original catalog records (`l10n_pt_vat`,
  `l10n_pt_vat_archive` and `l10n_pt_account_vat` namespaces) without
  recreating them; old business XMLIDs keep pointing at the same
  record ids.
- When only `l10n_pt_account_vat` is installed, the orphaned
  `account_vat_adjustment_norm` table and
  `account_move.vat_adjustment_norm_*` columns stay untouched in the
  database (protected by the VAT 20.0.1.2.0 pre-preserve-norms
  migration), so this addon can be installed later and expose the same
  records.

### Behavior (unchanged from the VAT implementation)

- Norm model: `name` required, `active`, `note` (translate),
  `out_refunds` "Customer Credit Notes", `in_refunds` "Vendor Credit
  Notes"; ordered `name, id`.
- ACLs: read for `account.group_account_invoice` and
  `account.group_account_readonly`, CRUD for
  `account.group_account_manager`.
- Selector on the move form after `journal_div`: visible only for PT
  customer/vendor credit notes, editable only in draft, direction
  domain, no quick-create, related note displayed.
- The norm is optional for credit notes; it supports VAT return
  reporting workflows and is not a new legal obligation. No annex or
  SAF-T generation is added.

## Non-goals

- No legal validations, field behavior changes, data defaults, SAF-T
  work or statutory annex exports.
- No AGPL reuse: all code here is newly authored under LGPL-3.

## Superseded decisions

### 2026-11-20 — independent norm model and install-time copy

The shared `account.vat.adjustment_norm` model is superseded by
`l10n.pt.vat.adjustment.norm` (table `l10n_pt_vat_adjustment_norm`),
and the move fields become `l10n_pt_vat_adjustment_norm_id` and
`l10n_pt_vat_adjustment_norm_note`. The legacy `l10n_pt_vat` keeps
its own `account.vat.adjustment_norm` model and catalog unchanged —
with no hooks or migrations — so this addon owns every row it exposes
and never aliases legacy-owned records.

`post_init_hook` replaces the earlier `pre_init_hook` XMLID
aliasing: at initial installation it copies the catalog rows — ids,
names, notes, flags — from the legacy `account_vat_adjustment_norm`
table when present, rewrites `account_move` links onto the new
column, and registers `l10n_pt_account_invoice.*` XMLIDs for the
copied records. It reads the `l10n_pt_vat`, `l10n_pt_vat_archive`
and `l10n_pt_account_vat` namespaces for source XMLIDs, has no
runtime dependency on any sibling, and is a no-op on databases
without the legacy table.

Install order: update `l10n_pt_vat` after the core upgrade, install
or update `l10n_pt_account_vat`, then install this addon — before
the optional `l10n_pt_vat` uninstall, which is only safe after the
copies are verified.

The hook runs at initial installation only; databases that already
run a preview build of this addon are not covered by a supported
release upgrade.

The model, field and hook names in the sections above are superseded
by this decision and kept here as history.

### 2026-11-20 — seeded statutory catalog and mapping-based install copy

Fresh installations now seed the standard statutory references: the
same legal-basis names, XMLID names and direction flags as the retired
`l10n_pt_vat` catalog, loaded `noupdate` so module updates preserve
user customizations.

On the first install over a database that still has the legacy
`account_vat_adjustment_norm` table, `post_init_hook` matches legacy
records to the seeded rows by XMLID name and reuses the seeded record
IDs. The seeded row then takes the legacy name, translated note,
active flag and direction flags, so customized legacy values win over
the seed defaults while the successor XMLIDs already point at the
right records. Legacy norms without a seeded match are imported with
newly allocated IDs, and credit-note links are rewritten through the
explicit old-to-new ID mapping — not by numeric ID equality.

This supersedes the earlier copy that preserved legacy IDs verbatim:
copying IDs could collide with the seeded catalog and the move-link
rewrite relied on ID equality.

## Tasks

- [x] Spec this split.
- [x] Scaffold addon: manifest, models, security, views, hooks, tests,
      readme fragments.
- [x] Trim `l10n_pt_account_vat` to the tax/snapshot/retirement scope.
- [x] Verify on a fresh disposable database: VAT install + tests,
      then invoice install + tests; pre-commit.
- [x] Verify that a VAT-only upgrade of a disposable 20.0.1.1.0 database
      preserves the norm and credit-note link until the invoice addon
      is installed, and that both original XMLIDs still resolve.
- [ ] Verify a complete upgrade from a real 19.0 database copy.
