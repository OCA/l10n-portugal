# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrVersion(models.Model):
    _inherit = "hr.version"

    l10n_pt_id_doc_type = fields.Selection(
        [
            ("cc", "Citizen Card"),
            ("bi", "Identity Card (BI)"),
            ("residence", "Residence Permit"),
            ("other", "Other"),
        ],
        string="ID Document Type",
        tracking=True,
        groups="hr.group_hr_user",
    )
    l10n_pt_id_doc_expiry = fields.Date(
        string="ID Document Expiry",
        tracking=True,
        groups="hr.group_hr_user",
    )
    l10n_pt_irct_id = fields.Many2one("l10n.pt.irct", string="IRCT", tracking=True)
    l10n_pt_professional_category_id = fields.Many2one(
        "l10n.pt.professional.category",
        string="Professional Category",
        tracking=True,
    )
    l10n_pt_union_id = fields.Many2one("l10n.pt.union", string="Union", tracking=True)
    l10n_pt_profession_id = fields.Many2one(
        "l10n.pt.profession", string="Profession (CPP)", tracking=True
    )
    l10n_pt_pay_grade_id = fields.Many2one(
        "l10n.pt.pay.grade", string="Pay Grade", tracking=True
    )
    l10n_pt_ss_regime_id = fields.Many2one(
        "l10n.pt.ss.regime",
        string="Social Security Regime",
        tracking=True,
        default=lambda self: self.env.ref(
            "l10n_pt_hr.l10n_pt_ss_regime_geral", raise_if_not_found=False
        ),
    )
    l10n_pt_disability_degree = fields.Integer(
        string="Disability Degree (%)", tracking=True
    )
    l10n_pt_qualification_level = fields.Selection(
        [(str(level), f"Level {level}") for level in range(1, 9)],
        string="Qualification Level (QNQ)",
        tracking=True,
    )
    l10n_pt_work_insurance_id = fields.Many2one(
        "l10n.pt.work.insurance",
        string="Work Insurance",
        tracking=True,
    )

    # Validate the Portuguese NISS (Numero de Identificacao da Seguranca
    # Social): 11 digits, first digit 1 (national) or 2 (foreign), last
    # digit a check digit over the first 10 with prime weights.
    @api.constrains("ssnid")
    def _check_ssnid(self):
        result = super()._check_ssnid()
        for version in self:
            niss = (version.ssnid or "").strip()
            if not niss or version.company_country_id.code != "PT":
                continue
            if not re.fullmatch(r"[12]\d{10}", niss):
                raise ValidationError(
                    self.env._(
                        "Invalid Social Security number %(niss)s: "
                        "the NISS must have 11 digits and start with 1 or 2.",
                        niss=niss,
                    )
                )
            weights = (29, 23, 19, 17, 13, 11, 7, 5, 3, 2)
            total = sum(
                int(digit) * weight
                for digit, weight in zip(niss[:10], weights, strict=False)
            )
            if int(niss[10]) != 9 - total % 10:
                raise ValidationError(
                    self.env._(
                        "Invalid Social Security number %(niss)s: "
                        "the check digit does not match.",
                        niss=niss,
                    )
                )
        return result

    # The SS regime is mandatory for employees of Portuguese companies;
    # it cannot be required at field level because hr.version rows may
    # predate the module (and non-PT companies have no regime).
    @api.constrains("l10n_pt_ss_regime_id", "company_id")
    def _check_l10n_pt_ss_regime(self):
        for version in self:
            if (
                version.company_country_id.code == "PT"
                and not version.l10n_pt_ss_regime_id
            ):
                raise ValidationError(
                    self.env._(
                        "The Social Security regime is required "
                        "for employees of Portuguese companies."
                    )
                )

    # Validate the worker's ID document: identification_id is checked
    # against the selected document type. Citizen Card = 12 chars (8 NIC
    # digits, the NIC check digit, a 2-char card version and a final
    # check digit); Identity Card (BI) = 9 digits (8-digit NIC plus its
    # check digit); residence permit and other = alphanumeric only. With
    # no type selected, employees of Portuguese companies are treated as
    # "other"; identification_id of other countries is not checked.
    @api.constrains("l10n_pt_id_doc_type", "identification_id", "company_id")
    def _check_l10n_pt_id_doc(self):
        for version in self:
            number = (version.identification_id or "").strip()
            if not number:
                continue
            doc_type = version._l10n_pt_effective_id_doc_type()
            if not doc_type:
                continue
            normalized = re.sub(r"\s+", "", number).upper()
            if doc_type == "cc":
                if not re.fullmatch(r"\d{9}[A-Z0-9]{2}\d", normalized):
                    raise ValidationError(
                        self.env._(
                            "Invalid Citizen Card number %(number)s: "
                            "it must have 12 characters (8 digits, a check "
                            "digit, a 2-character card version and a final "
                            "check digit).",
                            number=number,
                        )
                    )
                if int(normalized[8]) != self._l10n_pt_id_doc_nic_check(normalized):
                    raise ValidationError(
                        self.env._(
                            "Invalid Citizen Card number %(number)s: "
                            "the NIC check digit does not match.",
                            number=number,
                        )
                    )
                if not self._l10n_pt_id_doc_cc_luhn_valid(normalized):
                    raise ValidationError(
                        self.env._(
                            "Invalid Citizen Card number %(number)s: "
                            "the final check digit does not match.",
                            number=number,
                        )
                    )
            elif doc_type == "bi":
                if not re.fullmatch(r"\d{9}", normalized):
                    raise ValidationError(
                        self.env._(
                            "Invalid Identity Card (BI) number %(number)s: "
                            "it must have 9 digits.",
                            number=number,
                        )
                    )
                if int(normalized[8]) != self._l10n_pt_id_doc_nic_check(normalized):
                    raise ValidationError(
                        self.env._(
                            "Invalid Identity Card (BI) number %(number)s: "
                            "the check digit does not match.",
                            number=number,
                        )
                    )
            elif not re.fullmatch(r"[A-Z0-9]+", normalized):
                raise ValidationError(
                    self.env._(
                        "Invalid ID document number %(number)s: "
                        "only letters and digits are allowed.",
                        number=number,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._l10n_pt_normalize_identification_id()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"identification_id", "l10n_pt_id_doc_type", "company_id"} & vals.keys():
            self._l10n_pt_normalize_identification_id()
        return result

    def _l10n_pt_normalize_identification_id(self):
        for version in self:
            number = version.identification_id or ""
            if not number or not version._l10n_pt_effective_id_doc_type():
                continue
            normalized = re.sub(r"\s+", "", number).upper()
            if normalized != number:
                super(HrVersion, version).write({"identification_id": normalized})
        return True

    def _l10n_pt_effective_id_doc_type(self):
        self.ensure_one()
        if self.l10n_pt_id_doc_type:
            return self.l10n_pt_id_doc_type
        if self.company_country_id.code == "PT":
            return "other"
        return False

    @staticmethod
    def _l10n_pt_id_doc_nic_check(number):
        remainder = (
            sum(
                int(digit) * weight
                for digit, weight in zip(number[:8], range(9, 1, -1), strict=False)
            )
            % 11
        )
        return 0 if remainder < 2 else 11 - remainder

    @staticmethod
    def _l10n_pt_id_doc_cc_luhn_valid(number):
        total = 0
        for index, char in enumerate(reversed(number)):
            value = int(char) if char.isdigit() else ord(char) - 55
            if index % 2:
                value *= 2
                if value > 9:
                    value -= 9
            total += value
        return total % 10 == 0
