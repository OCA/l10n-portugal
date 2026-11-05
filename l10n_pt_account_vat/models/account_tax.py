# Copyright (C) 2026 Daniel Reis <dreis.pt@gmail.com>
# Copyright (C) 2026 Odoo S.A.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models

# https://info.portaldasfinancas.gov.pt/pt/apoio_contribuinte/Faturacao/Fatcorews/Documents/Tabela_Codigos_Motivo_Isencao.pdf
# Mirrors l10n_pt_certification (Odoo WIP, PR odoo/odoo#196102);
# drop when the core module lands.
L10N_PT_TAX_EXEMPTION_REASONS = [
    ("M01", "M01 - Artigo 16.º, n.º 6 do CIVA ou similar"),
    ("M02", "M02 - Artigo 6.º do Decreto-Lei n.º 198/90, de 19 de Junho"),
    ("M03", "M03 - Exigibilidade de caixa (revogado)"),
    ("M04", "M04 - Artigo 13.º do CIVA ou similar"),
    ("M05", "M05 - Artigo 14.º do CIVA ou similar"),
    ("M06", "M06 - Artigo 15.º do CIVA ou similar"),
    ("M07", "M07 - Artigo 9.º do CIVA ou similar"),
    ("M08", "M08 - IVA - autoliquidação (revogado)"),
    ("M09", "M09 - IVA - não confere direito a dedução"),
    ("M10", "M10 - IVA - Regime de isenção (Artigo 53.º do CIVA)"),
    ("M11", "M11 - Regime particular do tabaco"),
    ("M12", "M12 - Regime da margem de lucro - Agências de viagens"),
    ("M13", "M13 - Regime da margem de lucro - Bens em segunda mão"),
    ("M14", "M14 - Regime da margem de lucro - Objetos de arte"),
    ("M15", "M15 - Regime da margem de lucro - Objetos de coleção e antiguidades"),
    ("M16", "M16 - Artigo 14.º do RITI ou similar"),
    ("M19", "M19 - Outras isenções"),
    ("M20", "M20 - IVA - regime forfetário"),
    ("M21", "M21 - IVA – não confere direito à dedução"),
    ("M22", "M22 - IVA – não confere direito à dedução"),
    ("M25", "M25 - Mercadorias à consignação"),
    ("M30", "M30 - IVA - autoliquidação (2.1.i)"),
    ("M31", "M31 - IVA - autoliquidação (2.1.j)"),
    ("M32", "M32 - IVA - autoliquidação (2.1.l)"),
    ("M33", "M33 - IVA - autoliquidação (2.1.m)"),
    ("M40", "M40 - IVA - autoliquidação (6.6.a)"),
    ("M41", "M41 - IVA - autoliquidação (8.3.R)"),
    ("M42", "M42 - IVA - autoliquidação (21.2007)"),
    ("M43", "M43 - IVA - autoliquidação (362.99)"),
    ("M99", "M99 - Não sujeito; não tributado ou similar"),
]


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_pt_tax_exemption_reason = fields.Selection(
        selection=L10N_PT_TAX_EXEMPTION_REASONS,
        string="Tax Exemption Reason (PT)",
    )
