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

The rules are simplified placeholders: the IRS rule uses a flat withholding
rate and the Social Security base excludes the meal allowance. They are a
starting point for a full Portuguese payroll implementation, not a legally
accurate computation.
