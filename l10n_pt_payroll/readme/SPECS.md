# IRS withholding (retenção na fonte) — spec

**Status:** in progress — models, retention engine, 2026 CSVs for all three regions and
the official-xlsx converter implemented and verified **Date:** 2026-11-12 (updated
2026-11-20) **Scope:** `l10n_pt_payroll` in OCA/l10n-portugal. Owns the IRS retention
determinants on `hr.version` (moved here from `l10n_pt_hr`), the yearly table values and
the retention computation; `l10n_pt_hr` keeps only `l10n_pt_disability_degree` (also
needed by DMR-AT) and the `l10n.pt.irs.withholding.table` variant list. **Related:**
`l10n_pt_hr/readme/SPECS.md`, `l10n_pt_hr/readme/CONFIGURE.md`
(employee-side catalog).

## Context

`l10n_pt_payroll` computes IRS retention with the official withholding tables approved
each year by Despacho (e.g. n.º 233-A/2026 for the continente, n.º 1179/2026 for the
Açores, Despacho n.º 19/2026 RAM for Madeira, all for 2026). Each region publishes its
own I–XI tables; the tables change every year — sometimes mid-year (2026 saw a
retroactive rate cut via Decreto-Lei n.º 212/2026 and a November half-retention month
via Despacho n.º 12523-A/2026).

The module must make updating them cheap: the official tables ship as CSVs generated
from the AT Excel files, and an administrator can import a newer or corrected file
manually without a module release.

## Implemented so far

- `hr.pt.irs.withholding.table` — one bracket set per (date_start, region, table
  variant): `date_start`/`date_end` vigência, `region`, `table_id` →
  `l10n.pt.irs.withholding.table` (I–XI), set-level Despacho constants (`ias`,
  `disabled_dep_parcela_single`/`_joint`, `spouse_disabled_parcela`,
  `pension_dep_parcela_single`/`_joint`/ `_single_income`) and `line_ids`.
- `hr.pt.irs.withholding.line` — one bracket: `lower_bound`, `upper_bound` (empty =
  open-ended), `marginal_rate`, `parcela_abater` (safe_eval expression in `R`),
  `dependent_parcela`, `forces_disabled_parcela` (armed-forces pensioner flat deduction,
  tables X/XI), `effective_rate_limit` (informational).
- Retention engine on `hr.payslip._l10n_pt_irs_retention`, called by the `IRS` salary
  rule; `l10n_pt_irs_taxable` on `hr.salary.rule` is the share (0-1) of each rule total that enters `R`
  (currently only `BASIC`).
- `hr.pt.irs.withholding.import` wizard hosting the whole CSV import
  pipeline (`_import_csv_data` + validation/upsert helpers), the bundled
  loader and `post_init_hook` loading `data/irs/*.csv`.
- Bundled `data/irs/2026_{continente,acores,madeira}.csv` generated from the official AT
  workbooks (`Tabelas_RF_*_2026.xlsx` on the Portal das Finanças doclib) with
  `scripts/xlsx_to_csv.py`: 106/98/104 brackets, 11 variants each.
- `hr.version` IRS fields + tests (see below).
- Social Security rules driven by the employee's regime: `SS` (employee TSU)
  and `SS_COMP` (employer TSU) compute `BASIC x rate / 100` from
  `l10n.pt.ss.regime.l10n_pt_employee_rate` / `l10n_pt_employer_rate`
  (fields owned by `l10n_pt_hr` together with the regime records and their
  official values); `SAT_COMP` uses the `rate` field of the employee's
  `l10n.pt.work.insurance` policy (0 when no policy). Contribution base is
  still `BASIC` only — allowances are excluded, a documented simplification.
  FGS was abolished and is not modeled.

## Spec

### Retention computation

For each payslip:

```
R = sum of payslip line totals x l10n_pt_irs_taxable (taxable share)
table = hr.pt.irs.withholding.table covering payslip.date_from
        for (employee region, computed table variant)
bracket = the single line with lower_bound < R <= upper_bound
rate   = bracket.marginal_rate - (1.0 if dependents >= 3 else 0.0)   # n.5-h
        → replaced by l10n_pt_irs_preferred_rate when set           # n.5-e
parcela = safe_eval(bracket.parcela_abater, {"R": R})
        + bracket.dependent_parcela * n_dependents
        + disabled_dep_parcela_{single|joint} * n_disabled_dependents * factor   # n.5-a/n.6
        + spouse_disabled_parcela                                   # n.5-b
        + pension_dep_parcela_{single|joint|single_income} * n_dependents         # n.5-c
        + bracket.forces_disabled_parcela                           # n.5-d (X/XI)
retention = max(0, R * rate/100 - parcela)  →  truncated down to the euro
```

- **Non-resident** (`l10n_pt_irs_non_resident`): flat 25% of `R`, no table lookup, no
  deductions.
- **Preferred rate** (`l10n_pt_irs_preferred_rate`): replaces only the marginal rate
  (n.5-e); every parcela still applies.
- **Pensioner** (`l10n_pt_irs_pensioner`): resolves the VIII–XI variant through the same
  `l10n.pt.irs.withholding.table` mechanism; n.5-c per-dependent amounts and n.5-d
  armed-forces flat amount apply; n.5-a still applies per disabled dependent.
- **Disabled dependents**: n.5-a adds `disabled_dep_parcela_*` per dependent with
  disability ≥ 60%; n.6 lets the employee multiply it — up to 3× (single /
  married-single-income) or 6× (married joint), declared via
  `l10n_pt_irs_disabled_dep_factor` (constrained).
- **Disabled spouse** (n.5-b): `married_single_income` + spouse with disability ≥ 60%
  and no category A/H income → flat `spouse_disabled_parcela`.
- **Armed-forces disability** (n.5-d): pensioner + `l10n_pt_military_disabled` → flat
  `forces_disabled_parcela` on the bracket (tables X/XI only).
- **IRS Jovem** (art. 12.º-B CIRS, n.5-g): opt-in `l10n_pt_irs_jovem` + declared
  `l10n_pt_irs_income_years`. Exemption by income year: 100% / 75% (yrs 2–4) / 50% (yrs
  5–7) / 25% (yrs 8–10), capped at 55 × IAS per year; payroll withholds on the
  non-exempt portion `R − min(R, 55×IAS/14) × pct` — the `/14` monthly cap is the
  Despacho n.5-g approximation of the accumulated yearly exemption.
- Region resolves from `l10n_pt_irs_region` (auto-defaulted from the private address:
  state 20 → Açores, 30 → Madeira, 9xxx zip fallback); table set resolves by payslip
  date within `date_start`/`date_end`.
- No covering table → `UserError`, never a silent fallback.
- Bracket lookup must be deterministic: exactly one bracket per `R`.

### `hr.version` fields

- `l10n_pt_irs_family_status` — `single` / `married_single_income` / `married_joint`.
- `l10n_pt_irs_dependents` — IRS dependents (may differ from children).
- `l10n_pt_irs_disabled_dependents` — dependents with disability ≥ 60%.
- `l10n_pt_irs_disabled_dep_factor` — n.6 multiplier (1–3 or 1–6).
- `l10n_pt_irs_spouse_disabled` — n.5-b spouse case.
- `l10n_pt_military_disabled` — n.5-d armed-forces pensioner.
- `l10n_pt_irs_region` — `continente`/`acores`/`madeira`, computed default from address,
  manually overridable.
- `l10n_pt_irs_pensioner`, `l10n_pt_irs_non_resident`, `l10n_pt_irs_preferred_rate`,
  `l10n_pt_irs_jovem`, `l10n_pt_irs_income_years`.
- `l10n_pt_irs_table_id` — computed variant (I–XI), derived from family status +
  dependents + disability + pensioner flag.
- `l10n_pt_irs_taxable` Float on `hr.salary.rule` — taxable share multiplier (1.0 = fully taxable).

Kept in `l10n_pt_hr`: `l10n_pt_disability_degree` (DMR-AT needs it).

### CSV table files

- Bundled files live in `data/irs/<year>_<region>.csv`; file name is documentation —
  columns carry the keys.
- Header:
  `date_start,date_end,region,table_code,lower_bound, upper_bound,marginal_rate,parcela_abater,dependent_parcela, forces_disabled_parcela,effective_rate_limit,ias, disabled_dep_parcela_single,disabled_dep_parcela_joint, spouse_disabled_parcela,pension_dep_parcela_single, pension_dep_parcela_joint,pension_dep_parcela_single_income`
- `table_code` is the Roman variant I–XI; `date_start`/`date_end` give the Despacho
  vigência; set-level columns repeat on every row of a block and must be consistent
  inside it.
- Portuguese number formats (`1 234,56`, `44,95%`) are normalized at import;
  `parcela_abater` accepts expressions in `R`.
- **Official source:** the AT publishes Excel files per region on the Portal das
  Finanças doclib (`Tabelas_RF_*`). `scripts/xlsx_to_csv.py` converts them into the
  bundled CSV format (`inspect` dumps the layout, `convert` emits the CSV); the Despacho
  n.5 period constants are not in the workbook and are passed via `--set-json`.
  Transcription from the DR PDFs is the fallback.
- Adding a new Despacho = new CSVs (+ manifest data entry or module release);
  corrections = manual import.
- Bundled CSVs are append-only history: never delete an old year's files. Existing
  databases keep imported sets either way (the loader never deletes), but fresh installs
  only receive what is bundled — dropping an old file would break backdated payslips on
  new databases.

### Import

- Wizard `hr.pt.irs.withholding.import` owns `_import_csv_data`: upload CSV → validate → upsert per (date_start,
  date_end, region, variant) block; "Load bundled tables" re-imports `data/irs/*.csv`.
- Validation: required columns, known region/table codes, ordered numeric bounds
  contiguous from 0, last bracket open-ended, rates 0–100, `parcela_abater` parses under
  `safe_eval`, consistent set-level values per block, no partial writes on error.
- `post_init_hook` loads the bundled files at install.

## Statutory declarations — DMR (Segurança Social + AT)

### Context and legal frame

The **Declaração Mensal de Remunerações (DMR)** is a single monthly
obligation that simultaneously satisfies Segurança Social (contributions)
and the Autoridade Tributária (IRS withholding and deductions). It is
not two separate declarations: one submission reports, per worker, the
remuneration per earning code, the contribution rate code, the SS
contributions, the IRS retention, health-system and union deductions.

- Legal basis: Lei 110/2009 (Código dos Regimes Contributivos), DR
  1-A/2011, Portaria 307/2022 (SS model), Portaria 33/2024 (AT model,
  CIRS art. 119 n.1).
- Deadline: day 1–10 of the following month; August payslips extend to
  day 25. Delivery counts only when the system validates it.
- Channels: online only, via Segurança Social Direta or Portal das
  Finanças. Employers with **50+ workers must submit the file**
  ("Entregar ficheiro declaração de remunerações"); smaller employers
  may also use the portal's pre-filled/empty forms.
- Corrections: an error is fixed in the next month's declaration
  referencing the original month; later corrections need a standalone
  rectificativa (late filing).

### Data the module already owns

- `hr.version.ssnid` — NISS with PT check-digit validation (l10n_pt_hr).
- `l10n.pt.ss.regime` + `l10n_pt_dr_code` — the DR rate code per
  situação contributiva.
- IRS determinants on `hr.version` (family status, dependents, region,
  pensioner, Jovem...) and the computed table variant.
- Computed payslips with categorized lines (`BASIC`, `SA`, `SS`,
  `SS_COMP`, `IRS`, `SAT_COMP`, `NET`).

### Gaps to close

- **Earning/deduction codes**: the DMR reports remuneration per
  official *código de rendimento* (and deductions per código), not per
  salary rule. `l10n_pt_dmr_code` on `hr.salary.rule` stores the
  earning code per rule (same pattern as `l10n_pt_irs_taxable`, both
  editable on the rule form); deduction rubricas are identified by
  their rule codes/categories. Still needed: the official code table
  to populate values, and a mapping for codes not expressible per
  rule (e.g. holiday/Christmas subsidy splits, meal-subsidy taxable
  portion).
- **Worker-level DMR fields**: stored — NIF (`res.partner.vat` on the
  employee's work contact), NISS (`ssnid`), birth date
  (`hr.employee.birthday`), marital status (core `marital`), family
  status/dependents/disability (IRS fields), union + dues rate
  (`l10n.pt.union.l10n_pt_dues_rate`), regime + DR code, IRCT,
  profession, pay grade, work insurance. Remaining audit item: whether
  the AT facet needs fields beyond the IRS determinants (e.g. health
  subsystem affiliation).
- **Official file layouts**: the SS and AT DMR have distinct fixed
  file specifications (positions/fields per worker and per rubrica).
  The exact layouts must be obtained from Segurança Social / AT
  documentation (or sample files) before the exporter can be written.

### Proposed workflow (generation → review → submission)

1. **Generation phase** — a wizard (or scheduled action) per company +
   month creates a `l10n.pt.dmr.declaration` header (state `draft`)
   and one `l10n.pt.dmr.declaration.line` per worker × rubrica,
   populated from the period's validated payslips. Regeneration is
   allowed only while `draft`/`in_review`; once submitted it is locked.
2. **Review phase** — declaration lines are viewable/editable in
   form/list views (manual corrections flagged, e.g. a `manual`
   boolean + chatter tracking). Built-in checks block submission:
   missing NISS/NIF, regime without `l10n_pt_dr_code`, worker without
   payslip, negative rubricas, totals not reconciling with payroll.
3. **Submission phase** — options below; the declaration records the
   channel used, the file produced (attachment), submission timestamp
   and, when known, the validation result. A rectificativa is a new
   declaration referencing the corrected period.

### Implementation options for submission

- **A. File export (baseline, recommended first)** — generate the
  official DMR file(s) for download; the user uploads via Segurança
  Social Direta / Portal das Finanças. Works for all employer sizes,
  no credentials to manage, matches the mandatory channel for 50+
  workers. Blocked only on obtaining the official layout specs.
- **B. API/webservice submission** — research whether Segurança Social
  exposes a DMR webservice for certified software and whether AT
  offers an equivalent; if yes, add a submit action storing
  credentials per company. Uncertain availability — treat as a later
  increment, not a blocker.
- **C. Hybrid** — ship A first; design the declaration model so the
  exporter is one renderer among possible submitters (file now, API
  later). The generation/review phases are identical either way.

### Open questions

- Exact SS and AT DMR file layouts (field positions, rubrica code
  tables) — need official documentation or sample files from the user.
- Whether one file satisfies both SS and AT or two files/models are
  needed (the portal exposes "Preencher AT" / "Preencher SS" variants).
- Which rubrica codes apply to each PT payroll line (meal subsidy
  exempt vs taxable portion, holiday/Christmas pay, overtime...) —
  needs the official code table.
- Whether pre-reforma suspension (worker remits SS directly) appears
  in the DMR at all, and under which code.
- Multi-company: declaration is per employing entity — confirm
  `company_id` scoping covers all cases (single-entity employers are
  the norm; grouped employers need verification).

### Tasks

- [ ] Obtain official DMR file layouts + rubrica code tables (SS and AT)
      — data capture fields are in place; values pending user-provided docs.
- [x] Audit worker fields: NIF is the `vat` field on the work-contact
      partner; birth date, marital status, dependents and union
      affiliation already stored; union dues rate added as
      `l10n.pt.union.l10n_pt_dues_rate`.
- [x] `l10n_pt_dmr_code` on `hr.salary.rule` + editable on the rule
      form alongside `l10n_pt_irs_taxable`; values pending the official
      rubrica code table.
- [ ] `l10n.pt.dmr.declaration` + `.line` models, access, views.
- [ ] Generation wizard/batch from period payslips (draft → in_review).
- [ ] Review checks + manual-correction flagging.
- [ ] File exporter for the official layout(s) + download action.
- [ ] Submission tracking (channel, timestamp, validation result).
- [ ] Rectificativa support (declaration referencing corrected period).
- [ ] Research API/webservice submission feasibility (later increment).

## Contract details

- Money values are floats in euros; the payslip line is the negated, euro-truncated
  retention.
- `parcela_abater` expressions may only use `R` and numeric literals.
- Import is atomic per file.

## Alternatives considered

- **Tables as XML `<record>` data** — rejected: hundreds of rows per year × region ×
  variant is unreadable; CSV mirrors the source.
- **Native Odoo CSV import on lines** — rejected: cannot create parent sets, validate
  contiguity, or load bundled files.
- **`parcela_abater` as structured columns** — rejected: official expressions vary by
  row and year; the expression column is faithful.
- **Region derived from address only** — rejected as sole mechanism: fragile; explicit
  declared field with computed default is auditable.
- **Flat-rate fallback when no table covers the date** — rejected: silent wrong
  withholding is worse than a clear error.
- **Separate IRS module** — rejected (see discussion): table updates are already cheap
  via CSV + wizard; a split adds a dependency edge for no operational benefit. The
  `hr.pt.irs.withholding.*` models + `data/irs/` are self-contained if a split is ever
  needed.

## Open questions

- Jovem `/14` monthly cap is the Despacho n.5-g approximation; confirm against an
  official AT worked example (partial-year exemption accumulation is approximated).
- `l10n_pt_military_disabled` covers pensioners; whether armed- forces disability also
  affects work-income tables needs AT confirmation (n.5-d only references tables X/XI).
- Whether n.5-b `spouse_disabled_parcela` differs per region — resolved: the 2026
  Despachos for continente (233-A), Açores (1179) and Madeira (19 + Retificação 10)
  carry identical n.5 constants (€84.82/€42.41, €135.71, €42.86/€21.43/€34.29,
  €36.38/€18.19); per-set fields still guard future divergence.
- The zip-code fallback split for `l10n_pt_irs_region` needs verification against CTT
  postal tables.
- 2026 mid-year changes (DL 212/2026 retroactive cut, Despacho 12523-A/2026 November
  half-retention): whether to bundle corrected table sets or rely on manual import.

## Tasks

- [x] Move IRS employee fields from `l10n_pt_hr`; add region, disabled dependents,
      pensioner, non-resident, preferred rate, Jovem fields.
- [x] `hr.pt.irs.withholding.table`/`.line` models + access + views.
- [x] `l10n_pt_irs_taxable` Float on `hr.salary.rule` (BASIC = 1.0).
- [x] Retention engine per Despacho n.3/n.5 (brackets, dependent/
      disabled/spouse/pension/forces parcelas, n.5-e rate override, n.5-h 3+ dependents,
      n.6 factor, non-resident 25%, Jovem).
- [x] Bundle 2026 CSVs for continente, Açores and Madeira, generated from the official
      XLSX workbooks (Despachos 233-A/2026, 1179/2026, 19/2026 RAM + Retificação
      10/2026).
- [x] CSV import wizard + bundled loader + post-init hook.
- [x] Tests: payslip integration, preferred rate, non-resident, dependents + 3+
      reduction, disabled-dep factor, disabled spouse, Jovem, missing table, import
      validation, table derivation, region default.
- [x] `scripts/xlsx_to_csv.py`: official AT Excel → bundled CSV converter (`inspect` +
      `convert`), verified against all three 2026 workbooks; `dependent_parcela`,
      `forces_disabled_parcela` and `effective_rate_limit` extracted from the real
      layout; Despacho n.5 constants supplied via `--set-json` (not present in the
      workbooks).
- [x] `effective_rate_limit` transcription (populated from the workbooks).
- [x] Social Security rates configurable on `l10n.pt.ss.regime` (employee TSU,
      employer TSU) + SAT premium on the work insurance policy.
- [ ] SPECS/README regeneration if fragments change.
