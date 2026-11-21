# Default Portuguese absence types

**Status:** in progress **Date:** 2026-11-21 **Scope:** default `hr.leave.type` records
in `l10n_pt_hr_holidays`

## Default catalog

Install one separate Portuguese absence type for each active reason in Table 10 of the
2025 Relatório Único, covering Anexo 0, Group IX, field 4.1 (annual non-worked hours).
Preserve the leading zeros in the reference table. Do not seed the historical COVID
codes 16 and 17, which are valid only for reporting years 2020-2022. `Annual Leave`
remains a separate type and is not a Table 10 reason. The instructions exclude vacation,
Sundays, and public holidays from this section. Public holidays stay on work calendars.

| Table 10 | Stable XML ID suffix                        | English                              | Portuguese                                          | Request unit |
| -------- | ------------------------------------------- | ------------------------------------ | --------------------------------------------------- | ------------ |
| 01       | leave_type_work_accident                    | Work Accident                        | Acidente de trabalho                                | hour         |
| 02       | leave_type_certified_occupational_disease   | Certified Occupational Disease       | Doença profissional certificada                     | hour         |
| 03       | leave_type_uncertified_occupational_disease | Uncertified Occupational Disease     | Doença profissional não certificada                 | hour         |
| 04       | leave_type_non_occupational_illness         | Non-Occupational Illness             | Doença não profissional                             | hour         |
| 05       | leave_type_urgent_family_care               | Urgent Family Care                   | Assistência inadiável à família                     | hour         |
| 06       | leave_type_working_student                  | Working Student Absence              | Falta de trabalhador-estudante                      | hour         |
| 07       | leave_type_bereavement                      | Bereavement                          | Falecimento de cônjuge, parente ou afim             | hour         |
| 08       | leave_type_maternity                        | Maternity Leave                      | Licença por maternidade                             | day          |
| 09       | leave_type_paternity                        | Paternity Leave                      | Licença por paternidade                             | day          |
| 10       | leave_type_electoral_duties                 | Electoral Campaign or Polling Duties | Campanha eleitoral ou funções em mesa de voto       | hour         |
| 11       | leave_type_strike                           | Strike                               | Greve                                               | hour         |
| 12       | leave_type_worker_representation            | Worker Representation Duties         | Funções de representação coletiva dos trabalhadores | hour         |
| 13       | leave_type_employer_authorized              | Employer-Authorized Absence          | Ausência autorizada pelo empregador                 | hour         |
| 14       | leave_type_other_justified                  | Other Justified Absence              | Outra ausência justificada                          | hour         |
| 15       | leave_type_unjustified                      | Unjustified Absence                  | Ausência injustificada                              | hour         |

## Acceptance criteria

- Installation and upgrade provide exactly one record for each default XML ID in the
  table. Use Odoo's country scoping (`Portugal`, no company) and standard Time Off
  visibility. Leave existing core and user-created types alone. Do not overwrite HR
  changes to seeded records on upgrade.
- The new absence types require no allocation and are validated by a Time Off Officer.
  Validation records the absence; it does not grant or limit a statutory right. Allow
  hour-based records for partial absences and day-based records for maternity and
  paternity. These request units and the default native calendar behavior do not
  implement statutory eligibility or calendar-day entitlement rules.
- Portuguese names load from `pt.po`. Install without payroll. The seed records do not
  assign paid/unpaid status, Social Security treatment, or DMR codes.

## Future reporting integration

- Table 10 describes the reason, not whether the hours were paid. Anexo 0 fields 4.2/4.3
  distinguish remunerated and unremunerated hours. Leave type alone cannot establish
  those hours.
- Anexo A, field 24 uses Table 25 when October base pay was below base pay due because
  normal hours were unremunerated. This is a separate mapping. For example, Table 10
  reasons 02/03/04 may correspond to Table 25 reason 1 (illness), 08/09 to 2
  (parenthood), 01 to 3 (work accident), and 11 to 4 (strike), only when the reduction
  conditions hold. Do not use Table 25 as the list of Time Off types. Layoff and salary
  arrears must not be inferred from a generic leave type. Neither table is a DMR code
  list.
- Future reports should use stable IDs for defaults and support explicit mappings for
  company-specific types. Confirm the code table for the applicable reporting year and
  keep the exports and payroll bridge out of this slice.

Official sources:
[Relatório Único 2025 code workbook, Tables 10 and 25](https://download.gep.mtss.gov.pt/SGURI/downloads/Outras_tabelas_2025.zip)
and
[2025 completion instructions, pp. 9 and 13](https://download.gep.mtss.gov.pt/SGURI/downloads/Instrucoes_de_preenchimento_RU2025.zip).

## Alternatives considered

- Use a single generic absence: rejected because the captured data could not distinguish
  the required reporting reasons.
- Seed payable versus nonpayable versions of every reason: rejected because those are
  reporting outcomes, not necessarily different absence reasons.

## Tasks

- [x] Install and localize the default absence catalog.
- [ ] Implement and verify report-year mappings and aggregation when adding Relatório
      Único exports.
