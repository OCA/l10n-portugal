**Status:** draft

## Decisions

- The module catalogues the HR data elements required for Portugal, with the
  Portuguese term and the recommended English term for each. The catalog
  lives in `CONFIGURE.md`.
- Terminology follows official Portuguese sources: seg-social.pt for Social
  Security regimes and contribution brackets, OE/gov.pt for IRS brackets and
  withholding tables, QNQ/DGERT for qualification levels.
- Where Odoo CE/EE already ship a `pt` translation, it is reused; where the
  shipped term is a Brazilian variant (`holerite`, `auxílio-transporte`,
  `Licença`, `Escolaridade`), the European Portuguese term is recommended
  instead.
- Rejected: "Nível de Habilitações Académicas" — colloquial; the official
  term is "Nível de qualificação" (QNQ).
- Rejected: "Escalão de Remuneração" for employees — it applies to
  independent workers (trabalhadores independentes) on conventional
  remuneration; standard employees contribute on actual pay.
- The recurring statutory declarations are the monthly DMR-AT (AT) and
  DMR-SS (Segurança Social), both due by day 10 of the following month.
  Their required employee master data is catalogued in `CONFIGURE.md`.
- New fields are placed per the rules in `CONFIGURE.md` "Proposed fields":
  worker and contract-scoped data on `hr.version`, career-history data on
  `hr.employee`, per-year statutory tables in dedicated models, and
  salary-rule mappings in `l10n_pt_payroll`.
  - Rejected: a separate `l10n_pt.employee` model — duplicates `hr.version`
    and breaks the core versioning UI.
- Open-ended statutory value lists get one dedicated model each
  (`l10n.pt.collective.contract`, `l10n.pt.professional.category`, `l10n.pt.union`,
  `l10n.pt.profession`, `l10n.pt.pay.grade`) instead of one model per
  shared generic mechanism or `fields.Selection` for closed code tables.
  - Rejected: the generic `hr.employee.attribute` mechanism of
    `hr_employee_master_data` (OCA/hr) — the lists differ enough in shape (CPP is a
    ~2 700-entry coded classification, categories are scoped to an IRCT)
    that dedicated models stay simpler, and `l10n_pt_hr` stays independent
    of the generic addon.
- Escolaridade (`hr.employee.certificate`) and Nível de qualificação QNQ
  (`l10n_pt_qualification_level`) are distinct fields on distinct scales;
  both are kept. "Nível de Habilitações Académicas" is a colloquial umbrella
  term covering both — no separate field.
- Payroll-facing classifications are coded models, not Selection
  fields: `l10n.pt.ss.regime` (regimes of the Código dos Regimes
  Contributivos; codes are module-defined since SS publishes no numeric
  list) and `l10n.pt.irs.withholding.table` (official tables I–VII per the
  annual Despacho). `l10n_pt_payroll` maps each `code` to the year's
  contribution rates and withholding brackets.
  - Rejected: hardcoded Selection values — payroll needs a stable coded
    list it can extend and join against per-year rate tables.
- Work accident insurance (SAT) is a policy record
  (`l10n.pt.work.insurance`: insurer, policy number, coverage period)
  that employees reference from `hr.version` — several employees can share
  one employer policy. It matters most for independent workers, who hold
  their own policy; whether the employer's master policy also lands on
  `res.company` is an open question.
- Establishments are modelled by a dedicated `l10n.pt.establishment`
  model, not by fields on `hr.work.location`: the establishment is a
  company-level legal concept and the statutory grouping unit of both
  the DMR-SS file (per estabelecimento × taxa contributiva) and every
  Relatório Único anexo. The same record carries the SS `ESTABEE` code
  and the RU unidade-local data; `hr.work.location` links to it.
- DMR-AT campo 05 "local de obtenção" is only the geographic region
  (Continente/Açores/Madeira/Estrangeiro), not the establishment — the
  worker's region derives from the work location address.
- The PT master-data fields live on `hr.version` as typed Many2one
  fields over the dedicated `l10n.pt.*` models, so they are contract-scoped
  and versioned with the employment data. Effective-dated history for
  generic attributes remains the job of `hr_employee_master_data`
  (OCA/hr); `l10n_pt_hr` does not depend on it.
  - Rejected: effective-dated history for these fields via
    `hr.employee.history` — decided the values are contract-scoped data
    that belongs to `hr.version` like contract type and wage.

## Plan

- Iteration 1: extend demo data and translations for the elements marked
  **exists**.
- Iteration 2: add fields and data for the elements marked **new**, starting
  with worker identification (NIF, NISS, Cartão de Cidadão, residence permit)
  and the payroll inputs needed by `l10n_pt_payroll` (IRS brackets, TSU,
  Social Security scheme).

## Tasks

- [ ] Review the element catalog with a Portuguese payroll specialist.
- [ ] Add `pt_PT`-flavoured translations for the terms marked **exists**
  where the shipped translation is Brazilian.
- [x] Decide whether new fields go on `hr.employee`, `hr.version` or new
  models — decided; see "Proposed fields" in `CONFIGURE.md`.
- [ ] Implement the fields specified in `CONFIGURE.md` "Proposed fields",
  starting with `l10n.pt.establishment` and the `hr.version` worker
  identification fields.
- [ ] Decide where the entity-level RU fields (NISS, natureza jurídica,
  CAE, data de constituição) live — `res.company` here or `l10n_pt`.
- [x] Create the `hr_employee_master_data` module skeleton (`hr.employee.attribute`,
  `.value`, `.history`, `.change`) — see `CONFIGURE.md`; it stays a
  separate generic addon.
- [x] Decide whether `l10n_pt_hr` implements `hr.employee.*` first and
  extracts later, or depends on the module from the start — decided:
  `l10n_pt_hr` is self-contained with dedicated `l10n.pt.*` models and
  does not depend on `hr_employee_master_data`.
- [ ] Source CAE Rev. 4 and PT administrative divisions (distrito /
  município / freguesia) needed by the RU establishment block.
- [ ] Resolve the open questions listed at the end of `CONFIGURE.md`
  during the specialist review.
- [ ] Map salary rules to DMR-AT income codes and DMR-SS nature codes.
- [ ] Verify the master data checklist against the official DMR
  instructions (Portaria n.º 289/2025 for AT; SS file layout).
- [ ] Verify the Anexo A field list against the current Relatório Único
  instructions (field numbering changes between versions).
