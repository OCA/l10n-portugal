# Portuguese Establishments

**Status:** implemented (verified locally) **Date:** 2026-11-21 **Scope:** `l10n_pt_hr`
master data and contract assignment. Statutory exports are follow-up work. **Related:**
[Work Time Agreement](../../l10n_pt_payroll/specs/work-time-agreement.md).

## Requirements and sources

- **Local de trabalho** is the contractual place of work.
  [Labour Code articles 106(3)(b) and 193](https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2009-34546475)
  distinguish a fixed or predominant place from work across several locations.
  [Article 166](https://diariodarepublica.pt/dr/detalhe/lei/83-2021-175397114) requires
  the written telework agreement to specify the usual place of work. Neither means that
  a home or client site is an employer establishment.
- **Unidade local (estabelecimento)** is the employer unit in the
  [Relatorio Unico model](https://download.gep.mtss.gov.pt/SGURI/downloads/MODELO_RU.pdf).
  The reporting structure includes headquarters, and the unit data includes location,
  contacts, principal CAE and activity information. The
  [2025 instructions and SUL manual](https://www.relatoriounico.pt/ru/documents.seam)
  describe the DGCP unit identifier and the 31 October reference for Anexo A unit
  headcounts and CAE. Headcount inclusion and exclusions are report rules, not the count
  of assigned employees.
- **Estabelecimento in Social Security** has its own identity.
  [Legacy DMR-SS instructions](https://sisscontent.seg-social.pt/documents/10152/13321/normas_preenchimento_novo_formato/36e86fc2-5038-493e-8bf3-05a651f942f5/36e86fc2-5038-493e-8bf3-05a651f942f5)
  use four-character `ESTABEE` and group by establishment and contribution rate.
  [Social Security's SCC FAQ](https://www.seg-social.pt/ptss/pssd/documento/cmp40ps2i004gii2yseg4whju)
  schedules the transition to the new contribution cycle during 2026 and mandatory
  coverage from 1 January 2027. The
  [interoperability portal](https://www.plataformaservicos.seg-social.pt/psi/servicos.html)
  lists a separate **Transferir Local de Trabalho** service. Do not assume that legacy
  DMR grouping carries over to SCC.

## Proposed first release

- Add `l10n.pt.establishment` in `l10n_pt_hr`, with the English label **Establishment**
  and Portuguese label **Estabelecimento**. Keep **Work Location / Local de Trabalho**
  for Odoo's operational field. Avoid **Centro de Trabalho** for the statutory field.
- Each establishment belongs to the employing company. Store name, address/contact
  partner, optional principal CAE, opening/closing dates, and an archive flag. Provide
  an optional company default establishment, normally headquarters. That default is a
  data-entry setting, not a substitute for historical headquarters designation.
- Store optional **Social Security Establishment Code** and **Relatorio Unico Local Unit
  ID** as separate strings so leading zeros survive. Populate them from their respective
  portals. Do not infer one from the other or assume a permanent one-to-one mapping.
  Start with both identifiers on the establishment when they refer to the same unit.
  Confirm any real mismatch before adding an authority-specific assignment or mapping
  model.
- Store an explicit `l10n_pt_establishment_id` on `hr.version` and expose it on the
  employee form under **Work > Location**, alongside but independent of Odoo's address
  and work location. On new employee creation, use the employee company's configured
  default if it is active and the caller did not supply an assignment. An explicit
  selection or explicit empty value wins. A new version copies the previous assignment
  unless HR records a transfer. Do not recalculate saved assignments from work-location
  mappings or company defaults.
- Restrict selections to the employee's company and enforce that restriction on import
  as well as in the form. Show the field only for Portuguese companies. HR managers
  maintain establishments under Portugal HR Configuration and company administrators set
  the optional default on the company form. Archived units remain readable on historical
  versions and are not selectable for new assignments through the normal picker. Do not
  reparent an establishment or change an employee's company in place if that would
  invalidate an assigned establishment on any version; use a separate employee record
  for a different employer.
- Do not auto-assign existing employees to headquarters. Missing assignments are allowed
  in HR setup. A future export should identify missing or ambiguous statutory data
  instead of substituting the company's current default. A transfer in Odoo is not a
  submission to either authority.

## Acceptance and follow-up

- An employee working remotely or at a client site can retain an employer establishment
  without treating their home or the client site as a registered unit. Changing Odoo's
  Work Location does not move their statutory assignment.
- An employee transferred effective 1 November resolves to their old establishment on 31
  October and the new one on 1 November. Archiving the old establishment or changing the
  default does not alter that result.
- Multi-company users cannot assign another employer's establishment. Identifiers can be
  entered independently, and leading zeros are preserved.
- Demo data ships a Lisbon headquarters as the company default and a Porto branch.
  Helena Correia and Paulo Gonçalves are explicitly assigned to Porto while keeping the
  shared Lisbon work location. The other demo employees use the Lisbon default.
- [ ] Validate one multi-site company's SSD and SUL setup, including remote/mobile
      workers, real identifier mismatches and how each authority handles mid-month
      transfers or corrections. Do not assume a period-end assignment is sufficient.
- [x] Implement the master data and versioned assignment once reviewed.
- [ ] Specify each report/integration separately. Confirm reference-year schema,
      municipality/parish codes, historical headquarters and activity/CAE metadata, and
      whether address/identifier changes need dated history or export snapshots. Keep
      SCC workflow and any legacy DMR support in `l10n_pt_payroll`.
