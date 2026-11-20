Portuguese localization base for Payroll.

Features:

- A default "PT Payroll" salary structure (`l10n_pt_payroll.structure_pt`),
  with Portuguese salary rules adapted from the `payroll` module defaults:
  - *Vencimento Base* (`BASIC`): the contract wage.
  - *Subsídio de Alimentação* (`SA`): fixed meal allowance per worked day.
  - *Remuneração Bruta* (`GROSS`): base salary plus allowances.
  - *Segurança Social (Trabalhador)* (`SS`): 11% employee contribution.
  - *Retenção na Fonte IRS* (`IRS`): withholding tax.
  - *Segurança Social (Entidade Patronal)* (`SS_COMP`): 23.75% employer
    contribution.
  - *Líquido a Receber* (`NET`): gross minus deductions.
- Contribution registers for *Segurança Social* and
  *Autoridade Tributária e Aduaneira*.
- Demo data assigning the PT Payroll structure to the PT Company
  (`base.demo_company_pt`) employees provided by `l10n_pt_hr`.

- IRS withholding computed with the official progressive tables
  (Despacho n.º 233-A/2026 and regional equivalents), including the
  n.º 5 adjustments: dependents, disabled dependents/spouse, pensioner
  dependents, armed-forces disability, preferred rate, non-residents
  and IRS Jovem.
- Bundled 2026 withholding tables for all three regions
  (continente, Açores, Madeira) generated from the official AT Excel
  workbooks, importable/updatable through a wizard without a module
  release.

- Social Security contributions computed from the employee's regime
  (`l10n.pt.ss.regime`): employee TSU and employer TSU rates are
  configurable per regime, plus the work accident insurance (SAT)
  premium from the employee's insurance policy.

The contribution base is still simplified: it uses the base salary only
and excludes allowances such as the meal subsidy. That is a starting
point for a full Portuguese payroll implementation, not a legally
accurate computation.
