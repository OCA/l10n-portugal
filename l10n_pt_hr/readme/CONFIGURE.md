# Data elements required for Portugal

Catalog of the HR data elements the Portuguese localization needs, with the
Portuguese term, the recommended English term, and where the element maps in
Odoo. Terms marked **new** have no dedicated field or translation in Odoo CE
or EE today. Terms marked **exists** already have a `pt` translation in the
core `hr`, `hr_holidays`, `hr_attendance` or EE `hr_payroll` modules.

Terminology was checked against official sources (seg-social.pt, OE/gov.pt
tax tables, QNQ/DGERT) and against the `pt.po` files shipped with Odoo CE and
EE. Several shipped translations use Brazilian variants (`holerite`,
`auxílio-transporte`, `Licença` for time off); the PT-PT forms are preferred
here.

## Worker identification

| Element (PT) | English | Odoo element | Status |
| --- | --- | --- | --- |
| Número de Identificação Fiscal (NIF) | Tax identification number | employee contact VAT (`hr.employee.work_contact_id.vat` / private address `vat`) | exists (as VAT) |
| Número da Segurança Social (NISS) | Social security number | `hr.employee.ssnid` | exists — validated as NISS for PT companies |
| Cartão de Cidadão (n.º) | Citizen Card number | `l10n_pt_id_doc_type` = `cc` + core `identification_id` | implemented |
| Bilhete de Identidade (n.º) | Identity Card (BI, legacy) number | `l10n_pt_id_doc_type` = `bi` + core `identification_id` | implemented |
| Passaporte (n.º e validade) | Passport number and expiry | core `passport_id` / `passport_expiration_date` | exists |
| Título de Residência / Autorização de Residência (n.º e validade) | Residence permit number and expiry | `l10n_pt_id_doc_type` = `residence` + `identification_id` + `l10n_pt_id_doc_expiry` | implemented (format check only) |
| Estado civil | Marital status | `hr.employee.marital` | exists |
| Filhos dependentes | Dependent children | `hr.employee.children` | exists |
| Data de nascimento | Date of birth | `hr.employee.birthday` | exists |
| Naturalidade / País de nascimento | Place / country of birth | `hr.employee.place_of_birth`, `country_of_birth` | exists |
| Nacionalidade | Nationality | `hr.employee.country_id` (address) / new field | partial |
| Contacto de emergência | Emergency contact | `hr.employee.emergency_*` | exists |

## Employment relationship

| Element (PT) | English | Odoo element | Status |
| --- | --- | --- | --- |
| Tipo de contrato | Contract type | `hr.version.contract_type_id` | exists |
| Data de início / fim do contrato | Contract start / end date | `hr.version.contract_date_*` | exists |
| Período experimental | Probation period | `hr.version.trial_date_end` | exists |
| Horário de trabalho | Working schedule | `hr.version.resource_calendar_id` | exists |
| Local de trabalho | Work location | `hr.work.location` | exists (demo data) |
| Estabelecimento / Unidade local | Establishment / local unit | `l10n.pt.establishment`: `name`, `company_id`, `address_id`, `ss_establishment_code`, `ru_local_unit_id`, `principal_cae`, `date_start`/`date_end`, `active` | implemented |
| Seguro de Acidentes de Trabalho | Work accident insurance (SAT) | `l10n_pt_work_insurance_id` on `hr.version` → `l10n.pt.work.insurance` | new |
| Categoria profissional | Professional category | new field on `hr.version` | new |
| Escalão de remuneração | Pay grade | new field | new |
| Função / Cargo | Job position | `hr.job` / `hr.employee.job_id` | exists |

Notes on proposed terms:

- **Categoria profissional** is the term used on Portuguese payslips
  (recibo de vencimento) and in collective agreements. English: "professional
  category" ("job category" is also acceptable).
- **Escalão de remuneração** ("pay grade") is official for independent
  workers, whose contributions are computed on a "remuneração
  convencional" fixed in one of the pay grades (escalões) referenced to
  the IAS. It does not apply to employees on a standard contract (conta de
  outrem), whose contributions are a percentage of actual pay. Keep it
  only if the module targets independent workers.
- **Regime de Segurança Social** is the official term (seg-social.pt): e.g.
  "regime geral dos trabalhadores por conta de outrem", "regime dos
  trabalhadores independentes". English: "Social Security scheme".
- **Escalão de IRS** is official (OE tables, gov.pt): the IRS is divided into
  escalões (brackets). English: "IRS bracket" or "tax bracket". For payroll
  withholding, the operative table is the "tabela de retenção na fonte"
  (withholding table) — model the brackets behind it.
- **Nível de Habilitações Académicas**: prefer **Nível de qualificação**,
  the official term of the Quadro Nacional de Qualificações (QNQ, levels 1-8,
  aligned with EQF/ISCED). English: "qualification level". "Habilitações" is
  colloquial. Odoo CE ships `hr.employee.certificate` ("Certificate Level")
  translated as "Escolaridade" — European Portuguese users will expect the
  QNQ level.
- **Seguro de Acidentes de Trabalho**: official term for the mandatory work
  accident insurance; commonly abbreviated **SAT**. English: "work accident
  insurance" or "occupational accident insurance".

## Pay and statutory processing

| Element (PT) | English | Odoo element | Status |
| --- | --- | --- | --- |
| Vencimento base / Salário base | Base wage | `hr.version.wage`, salary rule `BASIC` | exists |
| Subsídio de alimentação | Meal allowance | salary rule | new (demo uses it) |
| Subsídio de transporte | Transport allowance | salary rule | new |
| Horas suplementares | Overtime | work entry type / salary rule | new (CE uses "Trabalho extra") |
| Estrutura salarial | Salary structure | `hr.payroll.structure` (EE `hr_payroll`; OCA `payroll`) | exists |
| Regra salarial | Salary rule | `hr.salary.rule` | exists |
| Categoria de rendimento | Income category (for IRS tables) | new field on salary rule | new |
| Registo de contribuições | Contribution register | `hr.contribution.register` | exists |
| Recibo de vencimento | Payslip | `hr.payslip` | exists (see note) |
| Processamento salarial | Payroll run / payslip batch | `hr.payslip.run` | exists |
| Retenção na fonte (IRS) | Withholding tax | salary rule + IRS table | new |
| Escalão de IRS | IRS bracket | new data (per year) | new |
| Tabela de retenção na fonte | Withholding table | new data (per year) | new |
| Regime de Segurança Social | Social Security scheme | new field on `hr.version` | new |
| Taxa Social Única (TSU) | Social security contribution | salary rule (employee 11%, employer 23.75%) | new |
| Base de incidência contributiva | Contribution base | salary rule computation | new |
| Autoridade Tributária e Aduaneira (AT) | Tax and Customs Authority | contribution register | new (used in `l10n_pt_payroll`) |
| Mínimo de existência | Subsistence minimum | IRS table parameter | new |
| Indexante dos Apoios Sociais (IAS) | Social benefits index | parameter for brackets | new |

Note: EE `hr_payroll` pt.po translates "Payslip" as both "Holerite"
(Brazilian) and "Recibo de Vencimento". In Portugal the document is the
"recibo de vencimento"; "holerite" is understood but not the local term.

## Time, leave and attendance

| Element (PT) | English | Odoo element | Status |
| --- | --- | --- | --- |
| Férias | Annual leave | `hr.leave.type` | new (CE uses "Licença") |
| Tipo de ausência | Time off type | `hr.leave.type` | exists (as "Tipo de folga") |
| Baixa médica | Sick leave | `hr.leave.type` | new |
| Licença parental | Parental leave | `hr.leave.type` | new |
| Horas suplementares | Overtime | `hr.attendance.overtime` | new |
| Ponto / Registo de assiduidade | Clock-in / attendance | `hr.attendance` | exists |
| Desligamento | Departure / termination | `hr.version.departure_*` | exists |
| Rescisão | Contract termination | departure reason | partial |

## Statutory reporting requirements

Portugal has no single annual "income declaration" from employer to worker
anymore. The recurring obligations are two monthly declarations, both due by
day 10 of the following month (Portaria n.º 33/2024 as amended by Portaria
n.º 289/2025 for the AT; the SS declaration follows the same calendar):

- **DMR-AT** — Declaração Mensal de Remunerações to the Autoridade
  Tributária e Aduaneira (AT): employment income (category A), IRS
  withholding, mandatory social protection contributions, union dues.
- **DMR-SS** — Declaração de Remunerações to Segurança Social, I.P.:
  remuneration per worker per month split by nature code.

Related obligations: payment of withheld IRS (day 20), payment of SS
contributions (days 1-25), the annual Relatório Único to DGCP (former GEP,
roughly March-April), and the payslip content required by art. 276.º of the
Código do Trabalho.

### Employee master data required by the DMR-AT

The DMR-AT quadro 5 ("Relação dos titulares dos rendimentos") is keyed by
the worker's NIF, with one line per income type and region of obtention:

| Field | Master data needed |
| --- | --- |
| NIF do titular | Tax identification number — the employee's contact VAT (`hr.employee.work_contact_id.vat` / private address `vat`) |
| Rendimentos do ano / anos anteriores | Payroll results per income code, split by year and region of obtention |
| Tipo de rendimento (código) | Income categorization on salary rules (e.g. A68 IRS Jovem, exempt codes) |
| Local onde foram obtidos | **Region only** — `C` Continente, `RA` Açores, `RM` Madeira, `E` Estrangeiro (Portaria n.º 274/2014 instructions; art. 17.º n.º 3 CIRS: where the work is performed). Derived from the work location address, not the establishment |
| Retenção de IRS | Withholding computed from the official tables |
| Contribuições obrigatórias | SS and health subsystem contributions |
| Quotizações sindicais | Union dues (if any) |
| Dias trabalhados | Worked days |
| Grau de incapacidade ≥ 60% | Disability flag (special declaration rule) |

The withholding itself depends on employee attributes declared to the AT
(not on the DMR): marital status / couple situation (tabela: não casado,
casado único titular, casado dois titulares), number of dependents,
disability, fiscal residence (Continente, Açores, Madeira), and IRS Jovem
eligibility (age, qualification level per QNQ, years of income).

### Employee master data required by the DMR-SS

The DMR-SS file has fixed-length records of 118 characters, model
`RC4008` (normas de preenchimento, seg-social.pt). The structure is:

- `R0` — file header (model + version), once per file.
- `R1` — entity header, **one per estabelecimento × taxa contributiva**.
- `R2` — remuneration lines per worker per month of reference.
- `R3` — totals closing each R1 block.

"Deverão existir tantos registos (R1) quantos os diferentes
estabelecimentos e diferentes taxas que a Entidade Empregadora tenha a
declarar" — the OCC practical guide (June 2025) states the same in plain
terms: workers of each estabelecimento go in separate declarations, and
one declaration per contribution rate. So the grouping key is
**(estabelecimento, taxa contributiva)**, not the worker alone. Each R1
carries `NISSEE` (SS number of the employing entity), `ESTABEE` (4-char
establishment code registered in Segurança Social Direta — SS rejects
unknown/closed codes, error DS31), `NIF`, `RAZSOC`, `DATREM`; each R3
carries the same keys plus `TAXA` and `TOTREGS`. A single file may
contain several R1–R3 blocks.

Each R2 line carries:

| Field | Master data needed |
| --- | --- |
| NISS | Social security number |
| Nome do trabalhador | Full name |
| Data de nascimento | Date of birth |
| Mês de referência | Payroll period |
| Dias de trabalho | Worked days (one decimal, may be negative) |
| Natureza da remuneração (código) | Remuneration nature per line: `P` base, `F` subsídio de férias, `N` subsídio de Natal, `R` subsídio de refeição, `S` trabalho suplementar, `T` trabalho noturno, `M` subsídios regulares mensais, `X` subsídios regulares não mensais, `C` comissões, `B`/`O` prémios mensais/não mensais, `A` ajudas de custo e transportes, `D` compensação por cessação, `2` férias pagas não gozadas, `6` diferenças de vencimento, `I` contrato intermitente |
| Valor e sinal | Amount per nature code (positive or negative) |
| Estabelecimento (`ESTABEE`) | SS establishment code of the employing entity — via the worker's establishment (`l10n.pt.establishment`) |
| Taxa contributiva | Contribution rate per worker (differs for MOE, independent workers, exemptions); also the second dimension of the R1/R3 grouping |

### Master data checklist for both declarations

- NIF (employee contact VAT), full name, date of birth, NISS — worker
  identification
- Marital status, number of dependents, disability, fiscal residence —
  IRS withholding table selection
- IBAN — salary payment and refund account
- Professional category — required on the recibo de vencimento (art. 276.º
  CT) and used in SS contexts
- Contract type, schedule — payslip; work location resolves the DMR-AT
  region and the DMR-SS/RU establishment
- Social Security scheme (regime) — determines the contribution rate and
  the applicable rules
- Union membership — quotizações sindicais
- Income categorization per salary rule — maps payroll lines to the DMR-AT
  income codes and DMR-SS nature codes

### Annual Relatório Único (RU) — DGCP

The Relatório Único (Portaria n.º 55/2010) is the annual social-activity
report to the DGCP (former GEP), delivered through the relatoriounico.pt
application, typically in a March-April window. It has a Rosto (employer and
establishments), Anexo A (Quadro de Pessoal — staff as of 31 October),
Anexo B (entries/exits during the year), Anexo C (continuous training),
Anexo D (occupational health and safety), Anexo E (strikes) and Anexo F
(service providers). Estagiários (interns) are included in the headcount
and the Anexo A.

### Establishments ("Unidades Locais") in the RU

The modelo RU (Portaria n.º 55/2010; modelo oficial `MODELO_RU.pdf`,
delivered via the SGURI platform at relatoriounico.pt) has a **Section II:
Identificação da(s) Unidade(s) Local(is) (Estabelecimentos)** — one
block per physical establishment *including the sede*. Each block needs:

| RU field | Data needed |
| --- | --- |
| Número da unidade local | Assigned by SGURI in the platform (SUL — Sistema de Unidades Locais); not master data |
| Nome / datas de início e fim | `l10n.pt.establishment.name`, activity period |
| Localização e contactos | Address down to freguesia + phone/email — via `address_id` |
| Actividade económica principal (CAE) | CAE Rev. 4 code — mandatory since the 2026 delivery (year 2025) |
| Situação perante a actividade, motivo e período | Status + reason + dates |
| Total de pessoas ao serviço (31 de Outubro) | Headcount snapshot per establishment |
| Número de trabalhadores por conta de outrem | TCO count per establishment |
| Natureza jurídica | Entity-level (`res.company`), repeated per block |

**Every anexo is keyed by unidade local**: Anexo A's header carries
NIF + NISS + *número da unidade local*, and each worker row has a "Nº da
unidade local (estabelecimento)" field. Anexos B–F are likewise reported
per UL (Anexo D even asks for SST technician counts per UL). This makes
the establishment — not the department — the statutory grouping unit of
the RU, and the 31-October reference date means the worker→establishment
assignment must be reconstructible historically (`hr.version`).

### Per-worker fields of the Anexo A "Quadro de Pessoal"

| RU field | Master data needed |
| --- | --- |
| Nome | `hr.employee.name` |
| NISS ou equiparado | Social security number; for public-sector workers without SS, the pension fund (CGA) subscriber number or beneficiary number |
| Regime de reforma aplicado | Pension/Social Security scheme applied — distinguishes SS regime from other regimes |
| Sexo | `hr.employee.gender` |
| Nascimento | `hr.employee.birthday` |
| Entrada na entidade empregadora | First contractual admission date (transfers keep the original date) |
| Última promoção | Last promotion date — no CE field; needs tracking |
| Tipo de contrato | `hr.version.contract_type_id` (RU code table) |
| Nacionalidade | Nationality — new dedicated field or country of the private address |
| Habilitação literária | Education level, using the RU code table (distinct from the QNQ level) |
| Situação na profissão | Situation in the profession (employee, employer, self-employed...) — new field |
| Categoria profissional | Professional category — required by art. 276.º CT on the payslip and here |
| Profissão (CPP) | Profession code from the CPP/2010 (Classificação Portuguesa das Profissões; RU Tabela 16) — new field |
| Nível de qualificação | QNQ level (field 15 in current versions) |
| PNT | Período normal de trabalho — the employee's contracted weekly working hours. A field on the employee/contract, not derived from `resource.calendar.hours_per_week` (that is the calendar's full-time equivalent) |
| Duração do tempo de trabalho | Full-time/part-time — part of the contract |
| Remuneração base devida/paga (outubro) | Payroll result for the reference month |
| Prémios e subsídios regulares, trabalho suplementar, prestações irregulares, horas não trabalhadas | Payroll aggregates for the reference year/month |

Anexo B additionally needs per-event data: admission and termination
dates, contract type, and reason for entry/exit. Anexo C needs per-worker
training records (course, hours, provider). Anexo D needs risk-prevention
and accident data per worker.

## Qualifications and career

| Element (PT) | English | Odoo element | Status |
| --- | --- | --- | --- |
| Escolaridade | Schooling / degree level | `hr.employee.certificate` | exists |
| Nível de qualificação (QNQ) | Qualification level | `l10n_pt_qualification_level` | new (complements `certificate`) |
| Área de formação | Field of study | `hr.employee.study_field` | exists |
| Certificações (RVCC) | Certifications | new | new |
| Categoria profissional (ver acima) | Professional category | see Employment relationship | new |

Note: "Nível de Habilitações Académicas" is a colloquial umbrella term; in
the catalog it maps to two distinct elements — **Escolaridade** (degree
level, `hr.employee.certificate`) and **Nível de qualificação** (QNQ
level 1–8). Both are listed above; no separate field is needed.

## Proposed fields

Concrete proposal for every element marked **new** or **partial** above.
Naming follows the `l10n_pt_` prefix used by sibling modules. All personal
data fields sit in the private-information group (`hr.group_hr_user`);
contract-scoped fields use `hr.group_hr_manager` where the core equivalent
does.

### Placement rules

- `hr.version` holds the employee's personal data in Odoo 19 (`ssnid`,
  `marital`, `children`, private address fields all live there). Fields
  that describe the worker or vary per contract version go there.
- `hr.employee` holds data that must survive contract changes: the first
  contractual admission date and the last promotion date.
- Per-year statutory tables (IRS brackets, IAS, minimum existence) get
  dedicated models; they are data, not employee fields.
- Open-ended statutory lists get one dedicated model each
  (`l10n.pt.collective.contract`, `l10n.pt.professional.category`, `l10n.pt.union`,
  `l10n.pt.profession`, `l10n.pt.pay.grade`) rather than one generic
  attribute mechanism or `fields.Selection`. Closed code tables stay
  `fields.Selection`. The module is self-contained: it does not depend on
  `hr_employee_master_data`.
- Salary-rule mappings (income category, DMR nature codes, contribution
  base) extend `hr.salary.rule` and therefore land in `l10n_pt_payroll`,
  not this module.
- Rejected: a separate `l10n_pt.employee` model — it would duplicate
  `hr.version` and break the core versioning UI.

### `hr.version` — worker identification

| PT element | Proposed field | Type | Required | Notes |
| --- | --- | --- | --- | --- |
| NIF | reuse `work_contact_id.vat` / private `vat` | — | yes for payroll | Validate PT NIF checksum in payroll, not here |
| NISS | `ssnid` | Char | yes for payroll | PT format + check-digit validation — see below |
| Documento de identificação — tipo | `l10n_pt_id_doc_type` | Selection: `cc` (Cartão de Cidadão), `bi` (Bilhete de Identidade), `residence` (Autorização de Residência), `other` (Outro) | recommended | Which document serves as the worker's ID; drives validation of the number field |
| Documento de identificação — número | reuse `identification_id` | Char (core) | recommended | Number of the selected document; normalized (uppercase, no spaces) and validated per type — see below |
| Documento de identificação — validade | `l10n_pt_id_doc_expiry` | Date | no | Expiry of the selected document |
| Nacionalidade | `l10n_pt_nationality_id` | Many2one `res.country` | no | Distinct from `private_country_id` (residence ≠ nationality); needed by Relatório Único |
| Situação fiscal (retenção) | `l10n_pt_tax_residence` | Selection: `pt` (Continente), `pt_acores`, `pt_madeira` | no | Drives the withholding table variant |
| Grau de incapacidade ≥ 60% | `l10n_pt_disability_degree` | Integer (%) | no | DMR-AT special declaration above 60% |

`ssnid` validation (NISS): implemented as a constraint on
`hr.version.ssnid`, applied only to employees of Portuguese companies
(`country_id = PT`) so other countries keep their own SSN conventions.
The NISS has 11 digits. The first digit identifies the
holder type (1 = national, 2 = foreign natural person — employees always
start with one of these). The last digit is a check digit computed over
the first 10 digits with prime weights `29, 23, 19, 17, 13, 11, 7, 5, 3,
2`: `check = 9 − (Σ dᵢ·pᵢ mod 10)`. Demo data uses mathematically valid
numbers. This validates format only — whether a NISS is actually
assigned is confirmed only by Segurança Social.

`identification_id` validation: the document number is stored in the
core `hr.version.identification_id` field. For employees of Portuguese
companies it is normalized (uppercase, no spaces) and checked against
the selected document type; with no type selected, PT employees are
treated as `other`. `identification_id` of other countries is neither
normalized nor validated.

Cartão de Cidadão: the document number is 12 characters, format
`DDDDDDDD C VV D` — 8-digit Número de Identificação Civil (NIC), its
check digit, a 2-character card version (`A–Z`, `0–9`), and a final
check digit. Two independent checks:

1. NIC check digit (9th char): mod-11 with weights 9..2 over the 8 digits —
   the same rule as the old BI and the NIF. `check = resto < 2 ? 0 :
   11 − resto`.
2. Final check digit (12th char): Luhn variant in base 36 over all 12
   chars, right to left, doubling every second character (`A`=10 … `Z`=35,
   subtract 9 when the doubled value ≥ 10); the sum must be a multiple of
   10.

Bilhete de Identidade (BI): the legacy document number is 9 digits —
the same 8-digit NIC (zero-padded) plus the same mod-11 check digit as
the CC's 9th character.

Residence permit and other document numbers have no Portuguese
check-digit scheme — format validation only (`A–Z`, `0–9`). Passports
are not part of `l10n_pt_id_doc_type`: they use the core
`hr.version.passport_id` / `passport_expiration_date` fields and are
not validated here.

### `hr.version` — employment relationship

| PT element | Proposed field | Type | Required | Notes |
| --- | --- | --- | --- | --- |
| Categoria profissional | `l10n_pt_professional_category_id` | Many2one `l10n.pt.professional.category`, filtered by the employee's IRCT | yes for payslip (art. 276.º CT) | Values are defined per IRCT; see note below |
| IRCT (CCT) | `l10n_pt_irct_id` | Many2one `l10n.pt.collective.contract` | recommended | Instrumento de Regulação Coletiva de Trabalho — the collective agreement (CCT is the common type). Determines the professional categories, working time and premiums; also RU Tabela 17 |
| Regime de Segurança Social | `l10n_pt_ss_regime_id` | Many2one `l10n.pt.ss.regime` | yes | Regime contributivo per the Código dos Regimes Contributivos (Lei 110/2009); determines contribution rate and rules |
| PNT (período normal de trabalho) | `l10n_pt_pnt_hours` | Float (hours/week) | no | Relatório Único field; default from `resource_calendar_id.hours_per_week` |
| Situação na profissão | `l10n_pt_profession_situation` | Selection per RU code table | no | Employee, employer, self-employed... |
| Habilitação literária | `l10n_pt_education_level` | Selection per RU code table | no | Distinct from QNQ level |
| Nível de qualificação (QNQ) | `l10n_pt_qualification_level` | Selection 1–8 | no | QNQ scale; complements `certificate` ("Escolaridade"), which is a different, degree-level scale. QNQ feeds IRS Jovem and RU |
| Situação familiar para IRS | `l10n_pt_irs_family_status` | Selection: `single` (não casado), `married_single_income` (casado — único titular), `married_joint` (casado — dois titulares) | no | Declared IRS family situation; core `marital` does not capture whether the spouse files jointly. Implemented in `l10n_pt_payroll` (tax domain) |
| Grau de incapacidade ≥ 60% | `l10n_pt_disability_degree` | Integer (%) | no | Selects the disabled withholding tables (IV–VII) and the DMR-AT special declaration |
| Dependentes para IRS | `l10n_pt_irs_dependents` | Integer | no | Number of IRS dependents — may differ from `children` (e.g. ascendentes); also feeds payroll's per-dependent deduction. Implemented in `l10n_pt_payroll` |
| Situação para retenção na fonte | `l10n_pt_irs_table_id` | Many2one `l10n.pt.irs.withholding.table` | computed | Official withholding table (I–VII for dependent work income) derived from the determinants above — implemented in `l10n_pt_payroll`; see note below |
| Quotização sindical | `l10n_pt_union_id` | Many2one `l10n.pt.union` | no | Declared on DMR-AT; dues amount is payroll data, not master data |
| Profissão (CPP) | `l10n_pt_profession_id` | Many2one `l10n.pt.profession` | no | Relatório Único field (Tabela 16); the record's `code` holds the CPP/2010 code. "CBO" is the Brazilian classification — not used in Portugal |
| Escalão de remuneração | `l10n_pt_pay_grade_id` | Many2one `l10n.pt.pay.grade` | no | Only if independent workers are in scope — see note above |
| Seguro de Acidentes de Trabalho | `l10n_pt_work_insurance_id` | Many2one `l10n.pt.work.insurance` | no | Work accident insurance (SAT) policy — insurer, policy number and coverage period live on the policy record; see note below |

Note on work accident insurance (SAT): `l10n.pt.work.insurance` is a
policy record (insurer, policy number, coverage period) that employees
point at — several employees can share one policy, which fits the common
case of an employer policy covering the whole staff. For employees on a
standard contract the coverage is the employer's obligation; the per-worker
link matters for independent workers (trabalhadores independentes), who
must hold their own SAT policy. Whether the employer's master policy also
belongs on `res.company` is an open question below.

Note on professional categories: each IRCT defines its own category table,
so `l10n.pt.professional.category` carries an optional `irct_id`. The
employee form filters the category list to the selected IRCT plus generic
categories (no IRCT).

Note on IRS withholding table selection: `l10n_pt_irs_table_id` is a
stored computed field implemented in `l10n_pt_payroll` — the employee
never picks a table directly. The
annual Despacho (e.g. n.º 1179/2026, Circular 3/2026) numbers the
dependent-work tables I–VII by exactly three determinants, all declared on
the employee: family situation (`l10n_pt_irs_family_status`), the number
of IRS dependents (`l10n_pt_irs_dependents` — a dedicated count, since IRS
dependents can differ from dependent children), and disability of 60% or
more (`l10n_pt_disability_degree`). Tables IV–VII are the disabled variants of
I–III. Caveats: these are the mainland (continente) tables — the Açores
and Madeira have their own Despacho table sets with the same numbering but
different values, which `l10n_pt_payroll` must select by region; non-resident
taxpayers pay a flat rate and pensioners use tables VIII–XI, both out of
scope here; IRS Jovem is a reduction computed by payroll (age, QNQ level,
years of income), not a table determinant.

### `l10n.pt.establishment` — estabelecimento / unidade local

Decided: a dedicated PT model, not fields on `hr.work.location`. The
establishment is a **company-level legal concept** — it is the grouping
unit of the DMR-SS file and of every RU anexo, its SS code is registered
in Segurança Social Direta against the employing entity, and it is
needed by non-HR flows (payroll, accounting, future SAF-T/IES
obligations). `hr.work.location` stays the HR-level "where the worker
physically is" record.

The same record serves both authorities, but the two identifiers are
independent: Segurança Social calls it the *estabelecimento*
(`ESTABEE`, a code registered in SS Direta), the RU calls it the
*unidade local* (SGURI assigns the número). They are stored as separate
fields and are never inferred from each other; values are plain text so
leading zeros survive. If a real-world mismatch ever appears (SS
grouping ≠ physical site), separate records remain possible.

| PT element | Field | Type | Required | Notes |
| --- | --- | --- | --- | --- |
| Nome / designação | `name` | Char | yes | RU Section II field 2 |
| Entidade empregadora | `company_id` | Many2one `res.company` | yes | The legal entity holding the NIF/NISS; cannot be moved to another company after creation |
| Morada | `address_id` | Many2one `res.partner` | yes | Same pattern as `hr.work.location`; must reach freguesia level for the RU — see open questions |
| Estabelecimento de Segurança Social (código) | `ss_establishment_code` | Char | no | `ESTABEE` in the DMR-SS R1/R2/R3 records; code registered in SS Direta, SS rejects unknown/closed codes (DS31) |
| Unidade local (número RU) | `ru_local_unit_id` | Char | no | SGURI-assigned local unit number; independent from the SS code |
| Actividade económica principal (CAE) | `principal_cae` | Char | no | CAE Rev. 4; RU Section II / Anexo A field — see open questions on the CAE table |
| Datas de início/fim | `date_start`, `date_end` | Date | no | Opening/closing dates of the establishment |
| Activo | `active` | Boolean | yes | Archived establishments stay readable on historical versions but cannot be selected for new assignments |

Worker assignment is stored directly on `hr.version.l10n_pt_establishment_id`
(mirrored on `hr.employee`), **not** derived from the work location.
`res.company.l10n_pt_default_establishment_id` only pre-fills the
assignment when an employee is created; it never reassigns existing
employees or past versions. History is preserved by core version
copying — a dated version keeps the establishment that was assigned at
that date. Whether head-office flag, activity-status fields, or a
`hr.work.location` link are still needed remains open.

Operator path: master data under **Employees ▸ Configuration ▸ Portugal ▸
Establishments**; the optional company default sits on the company form's
**General Information** page; the per-employee assignment is on the
employee form under **Work ▸ Location**.

Entity-level data repeated in the RU entity block (NISS da entidade,
natureza jurídica, data de constituição, CAE da entidade) belongs on
`res.company` — propose `l10n_pt_ss_number`, `l10n_pt_legal_nature`,
`l10n_pt_constitution_date`, `l10n_pt_cae_code` there; possibly better
placed in `l10n_pt` itself since accounting may need them too.

### `hr.employee` — career history

| PT element | Proposed field | Type | Required | Notes |
| --- | --- | --- | --- | --- |
| Admissão original (primeiro contrato) | `l10n_pt_first_contract_date` | Date | no | Manual; must not reset on internal transfer (RU Anexo A) |
| Última promoção | `l10n_pt_last_promotion_date` | Date | no | Candidate for a stored compute over `version_ids` job changes; manual is acceptable for v1 |

### New models

| Model | Purpose | Key fields |
| --- | --- | --- |
| `l10n.pt.establishment` | Estabelecimento / unidade local — statutory grouping unit of DMR-SS and all RU anexos | `name`, `company_id`, `address_id`, `l10n_pt_ss_establishment_code`, `is_head_office`, `l10n_pt_cae_code`, activity period/status |
| `l10n.pt.collective.contract` | Collective agreement (IRCT/CCT) | `name`, `code` (BTE/CCT reference), `sequence`, `active` |
| `l10n.pt.professional.category` | Professional category, optionally scoped to an IRCT | `name`, `code`, `irct_id`, `sequence`, `active` |
| `l10n.pt.union` | Trade union | `name`, `code`, `sequence`, `active` |
| `l10n.pt.profession` | Profession from the CPP/2010 classification | `name`, `code` (CPP code), `active` |
| `l10n.pt.pay.grade` | Escalão de remuneração (TI pay grade) | `name`, `code`, `sequence`, `active` |
| `l10n.pt.ss.regime` | Social security (contributory) regime — seeded with the regimes of the Código dos Regimes Contributivos | `name`, `code` (stable key; SS publishes no numeric codes — payroll maps code → rates), `sequence`, `active` |
| `l10n.pt.irs.withholding.table` | Official IRS withholding table variant — tables I–VII for dependent work income (VIII–XI are pension tables) | `name`, `code` (official Roman numeral per the annual Despacho), `sequence`, `active` |
| `l10n.pt.work.insurance` | Work accident insurance (SAT) policy | `insurer_id` (`res.partner`), `policy_number`, `date_start`, `date_end`, `active` |
| `hr.pt.fiscal.year` | Per-year statutory parameters | `year` (unique), `ias` (Indexante dos Apoios Sociais), `minimum_existence` |
| `hr.pt.irs.withholding.table` | Withholding brackets of one official table variant for a fiscal year and region (continente, Açores, Madeira have separate Despacho values) | `fiscal_year_id`, `region`, `table_id` (→ `l10n.pt.irs.withholding.table`), lines |
| `hr.pt.irs.withholding.line` | One withholding bracket | `table_id`, `lower_bound`, `upper_bound`, `rate`, `fixed_amount` |

The statutory lists use dedicated `l10n.pt.*` models instead of a generic
attribute mechanism: the lists differ enough in shape (CPP has ~2 700 coded
entries, professional categories are scoped to an IRCT, IRCTs have BTE
references) that one model per list stays simpler than a generic
attribute/value pair. The fields are stored on `hr.version`, so values are
contract-scoped and versioned like the rest of the employment data.
Both payroll-facing lists are coded models so `l10n_pt_payroll` can map
each `code` to its rates: `l10n.pt.ss.regime.code` → the regime's
contribution rates, `l10n.pt.irs.withholding.table.code` → the year's
withholding brackets. A
generic effective-dated attribute mechanism remains available in the
`hr_employee_master_data` module in the OCA/hr repository for attributes that do
not fit these dedicated lists; `l10n_pt_hr` does not depend on it.

The `hr.pt.irs.*` and `hr.pt.fiscal.year` models belong to `l10n_pt_payroll`
(they only matter once salary rules exist), but are listed here because they
consume the employee fields above. The IRS withholding tables — CSV data
files, manual import, and the retention computation — are specced in
`l10n_pt_payroll/readme/SPECS.md`. The `hr.salary.rule` extensions are:

| PT element | Proposed field on `hr.salary.rule` | Type | Notes |
| --- | --- | --- | --- |
| Categoria de rendimento (DMR-AT) | `l10n_pt_income_code` | Selection per AT code table | Maps rule to DMR-AT income codes (A68, exempt...) |
| Natureza da remuneração (DMR-SS) | `l10n_pt_ss_nature_code` | Selection: `P`, `F`, `N`, `R`, `S`, `T`, `M`, `X`, `C`, `B`, `O`, `A`, `D`, `2`, `6`, `I` | One code per rule; a rule may need splitting if it mixes natures |
| Base de incidência contributiva | `l10n_pt_contribution_base` | Selection/Boolean | Marks rules inside/outside the SS base; TSU rates (employee 11%, employer 23.75%) live on the rules themselves |

### Data, not fields

Some catalog elements need records rather than fields. These belong in data
files, not models:

- Leave types: `hr.leave.type` records for Férias, Baixa médica, Licença
  parental (PT-PT labels).
- Work entry types and salary rules for Horas suplementares, Subsídio de
  alimentação, Subsídio de transporte — defined by `l10n_pt_payroll`.
- QNQ and RU code tables — Selection values and demo data.
- CPP table — `l10n.pt.profession` rows, loaded from the official
  CPP/2010 classification (large table, import tooling needed).
- IRCT and per-IRCT professional category tables — `l10n.pt.collective.contract` and
  `l10n.pt.professional.category` rows per collective agreement.
- Escalões de remuneração (TI pay grades referenced to IAS) —
  `l10n.pt.pay.grade` rows, only if independent workers are supported.

### Open questions for the specialist review

- Whether `l10n_pt_nationality_id` should default from
  `private_country_id`.
- Whether `l10n_pt_last_promotion_date` is computed from version history or
  entered manually.
- Whether the seeded `l10n.pt.ss.regime` list matches the regimes
  Segurança Social expects on declarations, and whether official codes
  exist to replace the module-defined keys.
- Whether `l10n_pt_disability_degree` should distinguish the disability
  types the DMR-AT declaration requires.
- Exact selection values for `l10n_pt_profession_situation` against the
  current RU code table.
- How the CPP table is imported into `l10n.pt.profession` (size,
  hierarchy — the classification groups professions under categories).
- Whether `l10n.pt.pay.grade` needs a reference amount or IAS-linked
  value for independent workers.
- Whether the employer's master SAT policy should also be reachable
  from `res.company` (it is currently only reachable through the
  employees it covers).
- How to reach freguesia/município/distrito granularity for the RU
  address block — PT administrative-division data (`res.country.state`)
  or dedicated fields on the address/establishment.
- Whether the CAE needs a dedicated table/model (CAE Rev. 4 has ~2 700
  codes) or a simple list model like the ones above, and whether the
  entity-level and unit-level CAE are separate fields.
- Whether the entity-level RU fields (NISS, natureza jurídica, data de
  constituição, CAE) land on `res.company` in this module or in `l10n_pt`.

## HR Employee Master Data (`hr_employee_master_data`, OCA/hr)

The `hr_employee_master_data` module (OCA/hr) owns the whole
attribute mechanism: attribute definitions, allowed values, and
effective-dated per-employee assignments with full change history.
`l10n_pt_hr` seeds the Portuguese attributes as data and reads the
current values; it does not own the mechanism.

### Models

| Model | Purpose | Key fields |
| --- | --- | --- |
| `hr.employee.attribute` | A named list of allowed values for one HR data element | `name`, `code` (unique technical key), `employee_field_id` (optional link to an `hr.employee` field), `default_country_ids`, `required_country_ids`, `active` |
| `hr.employee.attribute.value` | One allowed value of an attribute | `attribute_id`, `name`, `code`, `reference` (record mirrored for many2one-linked attributes), `sequence`, `active`, `company_id` |
| `hr.employee.attribute.company` | Per-company activation of an attribute | `company_id`, `attribute_id`, `is_required` |
| `hr.employee.history` | One effective-dated assignment of an attribute value to an employee — the history record | `employee_id`, `attribute_id` (related, stored), `value_id`, `date_start`, `date_end`, `reason_id`, `is_current` |
| `hr.employee.change` | Transient wizard behind "Employee Change" | `employee_id`, `date_start`, `reason_id`, lines of `attribute_id` + `value_id` |
| `hr.employee.change.reason` | Coded change reason | `code`, `name`, `attribute_ids` |

### Attribute scope — countries and companies

Attributes are not global-on; they are scoped:

- `hr.employee.attribute.default_country_ids` — countries for which the
  attribute is a **default** (shown/applied unless the company turns it
  off). `required_country_ids` — countries for which it is **required**.
  The employee's country (company country by default) selects which
  attributes apply.
- `hr.employee.attribute.company` — each company keeps its own list of
  active attributes, and for each one whether it is **required** or
  **optional** for that company. This is the per-company override of the
  attribute's country defaults.

### Change reasons

`reason` on assignments and on the Employee Change wizard is a coded
`hr.employee.change.reason` record (`code`, `name`), not free text. Each
reason optionally lists the `hr.employee.attribute`s it applies to —
**empty means the reason applies to any attribute** (e.g. "Correction"
fits everything, "Promotion" may only fit `professional_category` /
`pay_grade` / `irct`).

### Assignment semantics

- An assignment is valid from `date_start` until the next assignment's
  `date_start` for the same employee and attribute (`date_end` computed,
  like `hr.version`). `is_current` means the period covers today.
- At most one current assignment per (employee, attribute) — partial
  unique constraint, same pattern as `hr.version`'s
  `(employee_id, date_version)` index.
- Writing a new assignment closes the previous current period
  (`date_end` = new `date_start`); overlaps are rejected.
- `reason_id` is a coded `hr.employee.change.reason` (see above); the
  reason's `attribute_ids` constrains which attributes it may be used
  with (empty = any).
- History is reconstructible for any date, not just today — this is what
  the RU 31-October snapshot and the monthly DMR-SS grouping consume.

### Employee form — Master Data page

A "Master Data" notebook page on `hr.employee` lists the employee's
master data as one line per attribute:

| Column | Source |
| --- | --- |
| Attribute | `hr.employee.attribute.name` |
| Current value | current assignment's `value_id` |
| Start date | current assignment's `date_start` |
| Change reason | current assignment's `reason` |

Only attributes with at least one assignment appear — an employee with
no union does not get an empty union line.

Row actions:

- **History** — opens the assignment list for that employee + attribute,
  all periods ordered by `date_start`.
- **Change** — opens the Employee Change wizard prefilled with that
  attribute (single-line change).

Page action:

- **Employee Change** — opens the wizard empty, for bulk changes.

### Employee Change (bulk)

The `hr.employee.change` wizard takes one `date_start` and one
`reason_id`, for the whole change, plus a list of (attribute, new
value) lines — the reason's `attribute_ids` must cover every attribute
in the change.
Confirming creates all assignments atomically and closes each previous
current period. Typical use: a promotion that changes professional
category, pay grade and IRCT on the same date in one recorded change.

A single-attribute change is the same wizard with one line — there is no
separate single-change model.

### Relationship to `l10n_pt_hr`

- `l10n_pt_hr` is self-contained: the PT lists are the dedicated
  `l10n.pt.*` models above, and the fields (`l10n_pt_irct_id`,
  `l10n_pt_professional_category_id`, `l10n_pt_union_id`,
  `l10n_pt_profession_id`,
  `l10n_pt_pay_grade_id`) are stored on `hr.version`, so they are
  contract-scoped and versioned with the rest of the employment data.
  There is no dependency on `hr_employee_master_data`.
- Coded list models (`l10n.pt.ss.regime`,
  `l10n.pt.irs.withholding.table`) feed payroll: each record's `code` is
  the stable key `l10n_pt_payroll` maps to contribution rates and
  withholding brackets per fiscal year.
- `hr_employee_master_data` remains available in the OCA/hr
  repository as an optional generic mechanism (effective-dated attribute assignments with
  change history) for HR data elements that do not fit the dedicated PT
  models; installing it does not change how `l10n_pt_hr` stores data.

### Open questions for `hr_employee_master_data`

- Whether assignments should also link to `hr.version` for attributes
  that are genuinely contract-scoped (e.g. a different IRCT per contract
  version) — v1 assumes employee-level only.
- Whether the Master Data page shows attributes with no assignments —
  the per-company `hr.employee.attribute.company` list decides which
  attributes are active at all; whether inactive-but-assigned or
  never-assigned attributes still appear needs a UX decision.
- Access rights: read for `hr.group_hr_user`, write for
  `hr.group_hr_manager` — same split as the private-info fields.
