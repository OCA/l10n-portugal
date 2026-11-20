# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestL10nPtHr(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.irct = cls.env["l10n.pt.irct"].create({"name": "CCT Teste"})
        cls.category = cls.env["l10n.pt.professional.category"].create(
            {"name": "Comercial", "irct_id": cls.irct.id}
        )
        cls.union = cls.env["l10n.pt.union"].create({"name": "Sindicato Teste"})
        cls.profession = cls.env["l10n.pt.profession"].create(
            {"name": "Comerciário", "code": "4190"}
        )
        cls.pay_grade = cls.env["l10n.pt.pay.grade"].create({"name": "Escalão 1"})

    def test_employee_pt_master_data(self):
        """An HR officer records the Portuguese master data of an employee:
        the collective agreement, professional category, union and CPP
        profession are stored on the employee's current contract version."""
        employee = self.env["hr.employee"].create(
            {
                "name": "Employee PT",
                "l10n_pt_irct_id": self.irct.id,
                "l10n_pt_professional_category_id": self.category.id,
                "l10n_pt_union_id": self.union.id,
                "l10n_pt_profession_id": self.profession.id,
                "l10n_pt_pay_grade_id": self.pay_grade.id,
            }
        )
        self.assertEqual(employee.l10n_pt_irct_id, self.irct)
        self.assertEqual(employee.l10n_pt_professional_category_id, self.category)
        self.assertEqual(employee.l10n_pt_union_id, self.union)
        self.assertEqual(employee.l10n_pt_profession_id, self.profession)
        self.assertEqual(employee.l10n_pt_pay_grade_id, self.pay_grade)

    def test_ss_regime_required_for_pt_only(self):
        """Employees of Portuguese companies must have a Social Security
        regime; employees of other countries may leave it empty."""
        pt_company = self.env["res.company"].create(
            {
                "name": "PT Test Company Regime",
                "country_id": self.env.ref("base.pt").id,
            }
        )
        regime = self.env.ref("l10n_pt_hr.l10n_pt_ss_regime_geral")
        employee = self.env["hr.employee"].create(
            {
                "name": "Employee PT Regime",
                "company_id": pt_company.id,
                "l10n_pt_ss_regime_id": regime.id,
            }
        )
        self.assertEqual(employee.l10n_pt_ss_regime_id, regime)
        with self.assertRaises(ValidationError):
            employee.l10n_pt_ss_regime_id = False
        # Non-PT companies are not constrained
        employee_other = self.env["hr.employee"].create(
            {"name": "Employee No Regime", "l10n_pt_ss_regime_id": False}
        )
        self.assertFalse(employee_other.l10n_pt_ss_regime_id)

    def test_employee_education_and_insurance(self):
        """An HR officer records the worker's QNQ qualification level and
        work accident insurance (SAT) policy on the employee."""
        insurer = self.env["res.partner"].create(
            {"name": "Seguradora Teste", "is_company": True}
        )
        insurance = self.env["l10n.pt.work.insurance"].create(
            {
                "insurer_id": insurer.id,
                "policy_number": "SAT-001",
                "date_start": "2026-01-01",
            }
        )
        self.assertEqual(insurance.display_name, "Seguradora Teste - SAT-001")
        employee = self.env["hr.employee"].create(
            {
                "name": "Employee PT 3",
                "l10n_pt_qualification_level": "6",
                "l10n_pt_work_insurance_id": insurance.id,
            }
        )
        self.assertEqual(employee.l10n_pt_qualification_level, "6")
        self.assertEqual(employee.l10n_pt_work_insurance_id, insurance)

    def test_employee_payroll_fields(self):
        """An HR officer records the worker's social security regime used
        by payroll."""
        regime_ti = self.env.ref("l10n_pt_hr.l10n_pt_ss_regime_ti")
        employee = self.env["hr.employee"].create(
            {
                "name": "Employee PT 4",
                "l10n_pt_ss_regime_id": regime_ti.id,
            }
        )
        self.assertEqual(employee.l10n_pt_ss_regime_id, regime_ti)
        # ss_regime is required and defaults to the general employee regime
        default_employee = self.env["hr.employee"].create({"name": "Employee PT 5"})
        self.assertEqual(
            default_employee.l10n_pt_ss_regime_id,
            self.env.ref("l10n_pt_hr.l10n_pt_ss_regime_geral"),
        )

    def test_niss_validation(self):
        """For a Portuguese company, the Social Security number must be a
        valid NISS: 11 digits starting with 1 or 2 and a correct check
        digit. Other countries' formats are not checked."""
        pt_company = self.env["res.company"].create(
            {
                "name": "PT Test Company",
                "country_id": self.env.ref("base.pt").id,
            }
        )
        # 12345678902 is a documented valid NISS
        employee = self.env["hr.employee"].create(
            {
                "name": "Employee PT 6",
                "company_id": pt_company.id,
                "ssnid": "12345678902",
            }
        )
        self.assertEqual(employee.ssnid, "12345678902")
        for invalid in ("12345678900", "92345678902", "12345"):
            with self.assertRaises(ValidationError):
                self.env["hr.employee"].create(
                    {
                        "name": "Employee PT Invalid",
                        "company_id": pt_company.id,
                        "ssnid": invalid,
                    }
                )
        # Non-PT companies keep their own SSN conventions
        self.env["hr.employee"].create(
            {"name": "Employee Other Country", "ssnid": "not-a-niss"}
        )

    def test_id_document_validation(self):
        """An HR officer records the worker's ID document; the number
        (the core identification_id field) is normalized for Portuguese
        employees and must pass the check digits of the selected document
        type. With no type, PT employees are treated as "other"; other
        countries' identification numbers are not touched."""
        pt_company = self.env["res.company"].create(
            {
                "name": "PT Test Company",
                "country_id": self.env.ref("base.pt").id,
            }
        )
        employee = self.env["hr.employee"].create(
            {
                "name": "Employee PT 7",
                "company_id": pt_company.id,
                "l10n_pt_id_doc_type": "cc",
                "identification_id": "12345678 9 zz1",
            }
        )
        self.assertEqual(employee.identification_id, "123456789ZZ1")
        employee.write({"identification_id": "111111110 zz2"})
        self.assertEqual(employee.identification_id, "111111110ZZ2")
        for invalid in ("123456780ZZ0", "123456789ZZ2", "12345678ZZ1"):
            with self.assertRaises(ValidationError):
                self.env["hr.employee"].create(
                    {
                        "name": "Employee PT 8",
                        "company_id": pt_company.id,
                        "l10n_pt_id_doc_type": "cc",
                        "identification_id": invalid,
                    }
                )
        bi = self.env["hr.employee"].create(
            {
                "name": "Employee PT 9",
                "company_id": pt_company.id,
                "l10n_pt_id_doc_type": "bi",
                "identification_id": "123456789",
            }
        )
        self.assertEqual(bi.identification_id, "123456789")
        for invalid in ("123456780", "12345"):
            with self.assertRaises(ValidationError):
                self.env["hr.employee"].create(
                    {
                        "name": "Employee PT 10",
                        "company_id": pt_company.id,
                        "l10n_pt_id_doc_type": "bi",
                        "identification_id": invalid,
                    }
                )
        residence = self.env["hr.employee"].create(
            {
                "name": "Employee PT 11",
                "company_id": pt_company.id,
                "l10n_pt_id_doc_type": "residence",
                "identification_id": "ab 12345",
                "l10n_pt_id_doc_expiry": "2030-01-01",
            }
        )
        self.assertEqual(residence.identification_id, "AB12345")
        self.assertEqual(str(residence.l10n_pt_id_doc_expiry), "2030-01-01")
        with self.assertRaises(ValidationError):
            self.env["hr.employee"].create(
                {
                    "name": "Employee PT 12",
                    "company_id": pt_company.id,
                    "l10n_pt_id_doc_type": "residence",
                    "identification_id": "AB-123",
                }
            )
        # With no document type, PT employees are treated as "other"
        with self.assertRaises(ValidationError):
            self.env["hr.employee"].create(
                {
                    "name": "Employee PT 13",
                    "company_id": pt_company.id,
                    "identification_id": "AB-123",
                }
            )
        other = self.env["hr.employee"].create(
            {
                "name": "Employee PT 14",
                "company_id": pt_company.id,
                "identification_id": "xy 1",
            }
        )
        self.assertEqual(other.identification_id, "XY1")
        # Other countries' identification numbers are not touched
        foreign = self.env["hr.employee"].create(
            {"name": "Employee Other Country", "identification_id": "AB-123 x"}
        )
        self.assertEqual(foreign.identification_id, "AB-123 x")
        # Moving the employee to a PT company re-validates the stored
        # number as "other" and rejects it
        with self.assertRaises(ValidationError):
            foreign.company_id = pt_company

    def test_fields_belong_to_contract_version(self):
        """The Portuguese master data is contract-scoped: it is stored on the
        employee's contract version, so a new contract version can carry
        different values."""
        employee = self.env["hr.employee"].create(
            {"name": "Employee PT 2", "l10n_pt_irct_id": self.irct.id}
        )
        version = employee.version_id
        self.assertEqual(version.l10n_pt_irct_id, self.irct)
        other_irct = self.env["l10n.pt.irct"].create({"name": "Other CCT"})
        version.write({"l10n_pt_irct_id": other_irct.id})
        self.assertEqual(employee.l10n_pt_irct_id, other_irct)
