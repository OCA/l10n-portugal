# l10n_pt_hr — spec and decision record

**Status:** implemented (core scope); open items listed under Tasks **Date:** 2026-11-14
**Scope:** `l10n_pt_hr` in OCA/l10n-portugal — Portuguese employee master data. Depends
only on `hr` and `l10n_pt`; deliberately independent from `hr_employee_master_data`
(which lives in OCA/hr as a generic, reusable framework).

## Context

Portuguese HR needs employee data that core `hr.employee` does not model: statutory
lists (IRCTs, professional categories, unions, CPP professions, pay grades, SS regimes,
IRS withholding table variants, work insurance policies) and per-worker values that must
be effective-dated. All of it lives on `hr.version` so values are contract-scoped and
versioned, and surface on `hr.employee` through core's `_inherits` delegation.

## Spec

### Statutory list models (`l10n.pt.*`)

- `l10n.pt.irct` — collective labour agreement (IRCT/CCT), with BTE code.
- `l10n.pt.professional.category` — professional category, linked to `irct_id` because
  each IRCT carries its own category table; generic categories have no IRCT.
- `l10n.pt.union`.
- `l10n.pt.profession` — CPP/2010 profession with the official 5-digit code (RU Tabela
  16). Only a small demo sample ships; the full ~2,700-entry classification is
  maintained by the customer — no bulk import is planned.
- `l10n.pt.pay.grade` — TI pay grade (escalão).
- `l10n.pt.ss.regime` — Social Security regime per the Código dos Regimes Contributivos
  (Lei 110/2009), one record per situação contributiva of the official SS
  contribution-rate table: `geral`, `pre_reforma` (pré-reforma with reduced working
  time), `moe_gerencia` / `moe_geral` / `moe_ipss` (the three MOE situations), `ti`,
  `mar`, `agricola`, `domestico`, `igrejas`, `facultativo`, `convergente`. `code`
  holds stable module keys. Each record also carries the official contribution
  rates (`l10n_pt_employee_rate`, `l10n_pt_employer_rate`,
  computed `l10n_pt_total_rate`) and the DR rate code (`l10n_pt_dr_code`) used by
  `l10n_pt_payroll` and future DMR declarations; transcribed so far: `geral`
  (000), `pre_reforma` (123), `moe_gerencia` (142), `moe_geral` (669),
  `moe_ipss` (183). Remaining regimes keep the general-regime field defaults
  until their official rates are added.
- `l10n.pt.irs.withholding.table` — the annual Despacho's I–XI variants: I–VII for
  dependent work income, VIII–XI for pensions. Only the variant identity lives here;
  the yearly bracket values are owned by `l10n_pt_payroll`.
- `l10n.pt.work.insurance` — SAT (work accident insurance) policy: insurer, policy
  number, coverage dates and `rate` (SAT premium % applied to the SS contribution
  base by `l10n_pt_payroll`). One policy record can be shared by many
  employees/versions — for employees the employer's master policy covers the staff,
  while independent workers hold their own.

### `hr.version` fields

`l10n_pt_irct_id`, `l10n_pt_professional_category_id`, `l10n_pt_union_id`,
`l10n_pt_profession_id`, `l10n_pt_pay_grade_id`, `l10n_pt_ss_regime_id` (required,
defaults to `geral`), `l10n_pt_disability_degree`, `l10n_pt_qualification_level` (QNQ
1–8), `l10n_pt_work_insurance_id`, `l10n_pt_id_doc_type`, `l10n_pt_id_doc_expiry`. All
`tracking=True`; HR-group restricted where sensitive.

`l10n_pt_disability_degree` stays here (not in payroll) because the DMR-AT Social
Security declaration needs it. The IRS retention determinants (family status,
dependents, region, rate premium) live in `l10n_pt_payroll`, which owns the computation
— see its `readme/SPECS.md`.

### NISS validation

`ssnid` is validated as a Portuguese NISS through core's `_check_ssnid` hook: exactly 11
digits, first digit `1` or `2`, check digit `9 − (Σ dᵢ·pᵢ mod 10)` over the first 10
digits with prime weights `29, 23, 19, 17, 13, 11, 7, 5, 3, 2`. Gated on
`company_country_id.code == "PT"`; empty values pass; non-PT companies keep their own
conventions. Format only — NISS assignment is confirmed by Segurança Social.

### ID document validation

The document number reuses core `identification_id`; the type is `l10n_pt_id_doc_type`
(`cc`, `bi`, `residence`, `other`). For PT companies the number is normalized on
create/write (uppercase, no spaces) via `super().write` to avoid re-entering the
constraint, then validated per type:

- **cc** — 12 chars `DDDDDDDD C VV D`: NIC mod-11 check digit (weights 9..2), 2-char
  card version, final Luhn-style check digit.
- **bi** — 9 digits: 8-digit NIC + its mod-11 check digit.
- **residence/other** — alphanumeric only.

With no type selected, PT employees are treated as `other`; non-PT `identification_id`
values are neither normalized nor checked. Passport uses core
`passport_id`/`passport_expiration_date`.

### Deliberate exclusions

- Union dues amount is payroll data, not master data — no field.
- Nível de Habilitações Académicas is covered by core `hr.employee.certificate`
  (Escolaridade) plus `l10n_pt_qualification_level` (QNQ); "habilitações" was rejected
  as colloquial.
- IRS table _values_ (brackets, rates, yearly Despacho) belong to `l10n_pt_payroll`, not
  here.

## Contract details

- Everything hangs off `hr.version`: writes are versioned, so a change of IRCT or regime
  mid-contract creates a new version like any other contract field.
- `l10n.pt.professional.category` domain on the employee form filters to the selected
  IRCT plus generic categories.
- Validation errors are user-facing `ValidationError`s in English; PT translations
  belong in `i18n/` (the .pot is stale — regenerate on next i18n pass).

## Alternatives considered

- **Generic attribute framework for PT data** — rejected: the user requirement was a
  self-contained localization independent from `hr_employee_master_data`; dedicated
  fields give typing, tracking and views for free.
- **Flat fields for SAT (insurer/policy/dates on `hr.version`)** — rejected: a policy is
  a reusable record shared across employees; the M2o keeps master data normalized.
- **IRS table as a manually chosen field** — rejected: the variant is fully determined
  by family status, dependents and disability; it is computed, never declared.

## Open questions

- Whether the employer's master SAT policy should also live on `res.company` for
  company-level reporting.
- Exact SS regime list may grow (public-sector regimes) — `code` keys are stable, data
  updates don't need schema changes.

## Tasks

- [x] Dedicated `l10n.pt.*` statutory list models + seed data
- [x] `hr.version` fields, employee form group, menus, access rights
- [x] NISS validation + demo data
- [x] ID document type/number/expiry on core `identification_id`
- [x] SAT as shared policy model
- [x] IRS determinants moved to `l10n_pt_payroll`
- [x] Demo professions (CPP sample) + employee assignments
- [ ] i18n `.pot` regeneration
- [ ] PT translations
