# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestL10nPtHr(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.irct = cls.env["l10n.pt.collective.contract"].create({"name": "CCT Teste"})
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
        other_irct = self.env["l10n.pt.collective.contract"].create(
            {"name": "Other CCT"}
        )
        version.write({"l10n_pt_irct_id": other_irct.id})
        self.assertEqual(employee.l10n_pt_irct_id, other_irct)


class TestL10nPtEstablishment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env["res.company"].create(
            {
                "name": "PT Establishment Company A",
                "country_id": cls.env.ref("base.pt").id,
            }
        )
        cls.company_b = cls.env["res.company"].create(
            {
                "name": "PT Establishment Company B",
                "country_id": cls.env.ref("base.pt").id,
            }
        )
        cls.address = cls.env["res.partner"].create(
            {
                "name": "Establishment Address",
                "street": "Rua Augusta 1",
                "city": "Lisboa",
            }
        )

    def _create_establishment(self, company, name="Estabelecimento", **values):
        return self.env["l10n.pt.establishment"].create(
            {
                "name": name,
                "company_id": company.id,
                "address_id": self.address.id,
                **values,
            }
        )

    def test_company_default_assigns_establishment_on_hire(self):
        """A Portuguese company's default establishment is pre-assigned to
        new employees; an explicit choice overrides it, an explicit empty
        value stays empty, and archiving the default leaves new hires
        unassigned."""
        site_default = self._create_establishment(self.company_a, "Sede A")
        site_other = self._create_establishment(self.company_a, "Filial A")
        self.company_a.l10n_pt_default_establishment_id = site_default

        employee = self.env["hr.employee"].create(
            {"name": "Worker Default", "company_id": self.company_a.id}
        )
        self.assertEqual(employee.l10n_pt_establishment_id, site_default)

        explicit = self.env["hr.employee"].create(
            {
                "name": "Worker Explicit",
                "company_id": self.company_a.id,
                "l10n_pt_establishment_id": site_other.id,
            }
        )
        self.assertEqual(explicit.l10n_pt_establishment_id, site_other)

        empty = self.env["hr.employee"].create(
            {
                "name": "Worker Empty",
                "company_id": self.company_a.id,
                "l10n_pt_establishment_id": False,
            }
        )
        self.assertFalse(empty.l10n_pt_establishment_id)

        site_default.active = False
        unassigned = self.env["hr.employee"].create(
            {"name": "Worker Archived Default", "company_id": self.company_a.id}
        )
        self.assertFalse(unassigned.l10n_pt_establishment_id)

    def test_default_follows_employee_company_not_active_company(self):
        """With both companies allowed and company B active, an employee
        created explicitly for company A still gets company A's default
        establishment, not the active company's."""
        site_a = self._create_establishment(self.company_a, "Sede A")
        site_b = self._create_establishment(self.company_b, "Sede B")
        self.company_a.l10n_pt_default_establishment_id = site_a
        self.company_b.l10n_pt_default_establishment_id = site_b

        employee = (
            self.env["hr.employee"]
            .with_company(self.company_b)
            .create(
                {"name": "Worker Explicit Company", "company_id": self.company_a.id}
            )
        )
        self.assertEqual(employee.company_id, self.company_a)
        self.assertEqual(employee.l10n_pt_establishment_id, site_a)

    def test_establishment_history_is_versioned(self):
        """The establishment assigned on a contract version stays fixed for
        that period: a later version can carry a different establishment,
        archiving the old site, changing the company default and the work
        location do not rewrite history, and a new dated version copies the
        current assignment."""
        site_old = self._create_establishment(self.company_a, "Sede Antiga")
        site_new = self._create_establishment(self.company_a, "Sede Nova")
        site_default = self._create_establishment(self.company_a, "Nova Predefinição")
        location_partner = self.env["res.partner"].create(
            {"name": "Loja Centro", "street": "Rua da Prata 2"}
        )
        location = self.env["hr.work.location"].create(
            {
                "name": "Loja Centro",
                "address_id": location_partner.id,
                "company_id": self.company_a.id,
            }
        )
        employee = self.env["hr.employee"].create(
            {
                "name": "Worker History",
                "company_id": self.company_a.id,
                "date_version": date(2026, 1, 1),
                "l10n_pt_establishment_id": site_old.id,
            }
        )
        first_version = employee._get_version(date(2026, 1, 1))
        self.assertEqual(first_version.l10n_pt_establishment_id, site_old)

        employee.create_version(
            {
                "date_version": date(2026, 11, 1),
                "l10n_pt_establishment_id": site_new.id,
            }
        )
        self.assertEqual(
            employee._get_version(date(2026, 10, 31)).l10n_pt_establishment_id,
            site_old,
        )
        self.assertEqual(
            employee._get_version(date(2026, 11, 1)).l10n_pt_establishment_id,
            site_new,
        )

        site_old.active = False
        self.company_a.l10n_pt_default_establishment_id = site_default
        employee.work_location_id = location

        self.assertEqual(
            employee._get_version(date(2026, 10, 31)).l10n_pt_establishment_id,
            site_old,
        )

        employee.create_version({"date_version": date(2026, 12, 1)})
        self.assertEqual(
            employee._get_version(date(2026, 12, 1)).l10n_pt_establishment_id,
            site_new,
        )

    def test_cross_company_assignment_is_rejected(self):
        """An establishment can only be assigned within its own company:
        writing a foreign site on the employee and setting a foreign site as
        the company default are both rejected."""
        site_a = self._create_establishment(self.company_a, "Sede A")
        site_b = self._create_establishment(self.company_b, "Sede B")

        employee = self.env["hr.employee"].create(
            {
                "name": "Worker Cross",
                "company_id": self.company_a.id,
                "l10n_pt_establishment_id": site_a.id,
            }
        )
        with self.assertRaises(UserError):
            employee.write({"l10n_pt_establishment_id": site_b.id})

        with self.assertRaises(UserError):
            self.company_a.l10n_pt_default_establishment_id = site_b

        # Aligning the writable version company with the foreign site does
        # not bypass the check against the employee's real company.
        with self.cr.savepoint(), self.assertRaises(UserError):
            employee.version_id.write(
                {
                    "company_id": self.company_b.id,
                    "l10n_pt_establishment_id": site_b.id,
                }
            )

    def test_employee_cannot_move_company_with_establishment(self):
        """An employee with an establishment assignment cannot be moved to
        another company; a separate employee record is required instead."""
        site_a = self._create_establishment(self.company_a, "Sede A")
        self.company_a.l10n_pt_default_establishment_id = site_a
        employee = self.env["hr.employee"].create(
            {"name": "Worker Move", "company_id": self.company_a.id}
        )
        self.assertEqual(employee.l10n_pt_establishment_id, site_a)
        with self.assertRaises(ValidationError):
            employee.write({"company_id": self.company_b.id})

    def test_establishment_security_and_identifiers(self):
        """Record rules restrict establishments to the user's companies,
        HR officers get read-only access while managers can maintain them,
        and leading-zero identifiers are preserved as plain text."""
        site_a = self._create_establishment(
            self.company_a,
            "Sede A",
            ss_establishment_code="0012",
            ru_local_unit_id="0007",
        )
        site_b = self._create_establishment(self.company_b, "Sede B")
        self.assertEqual(site_a.ss_establishment_code, "0012")
        self.assertEqual(site_a.ru_local_unit_id, "0007")

        manager = self.env["res.users"].create(
            {
                "name": "HR Manager A",
                "login": "hr_manager_a_est",
                "company_id": self.company_a.id,
                "company_ids": [(6, 0, [self.company_a.id])],
                "group_ids": [(6, 0, [self.env.ref("hr.group_hr_manager").id])],
            }
        )
        establishments = self.env["l10n.pt.establishment"].with_user(manager)
        self.assertIn(site_a, establishments.search([]))
        self.assertFalse(establishments.search([("id", "=", site_b.id)]))

        officer = self.env["res.users"].create(
            {
                "name": "HR Officer",
                "login": "hr_officer_est",
                "company_id": self.company_a.id,
                "company_ids": [(6, 0, [self.company_a.id])],
                "group_ids": [(6, 0, [self.env.ref("hr.group_hr_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            self.env["l10n.pt.establishment"].with_user(officer).create(
                {
                    "name": "Forbidden",
                    "company_id": self.company_a.id,
                    "address_id": self.address.id,
                }
            )

    def test_system_user_reads_own_company_establishments(self):
        """A system administrator without HR membership can read the
        establishments of their own company — needed to pick the company
        default — while other companies' establishments stay hidden and
        the read-only grant does not allow creating records."""
        site_a = self._create_establishment(self.company_a, "Sede A")
        site_b = self._create_establishment(self.company_b, "Sede B")
        sysadmin = self.env["res.users"].create(
            {
                "name": "System Admin A",
                "login": "sysadmin_a_est",
                "company_id": self.company_a.id,
                "company_ids": [(6, 0, [self.company_a.id])],
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("base.group_system").id,
                        ],
                    )
                ],
            }
        )
        establishments = self.env["l10n.pt.establishment"].with_user(sysadmin)
        self.assertIn(site_a, establishments.search([]))
        self.assertFalse(establishments.search([("id", "=", site_b.id)]))
        with self.assertRaises(AccessError):
            establishments.create(
                {
                    "name": "Forbidden",
                    "company_id": self.company_a.id,
                    "address_id": self.address.id,
                }
            )
