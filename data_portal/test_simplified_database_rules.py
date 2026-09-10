from types import SimpleNamespace

from django.test import TestCase

from data_portal.simplified_rules import (
    validate_simplified_business_rules,
)
from institutions.models import (
    Municipality,
    School,
)


def student_row(
    municipality,
    state,
    school_name="Escola Municipal Horizonte",
    inep_code="26037289",
):
    return {
        "_row": 2,
        "escola": school_name,
        "codigo_inep": inep_code,
        "endereco": "Rua Exemplo, 100",
        "cep": "56380000",
        "municipio": municipality,
        "estado": state,
        "tipo": "Urbana",
        "turma": "A",
        "serie": "EF02",
        "turno": "Manhã",
        "ano_letivo": 2026,
        "matricula": "20260001",
        "nome_aluno": "Ana Beatriz Silva",
    }


class SimplifiedDatabaseRulesTest(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.municipality = (
            Municipality.objects.create(
                name="Santa Maria da Boa Vista",
                state="PE",
            )
        )
        cls.other_municipality = (
            Municipality.objects.create(
                name="Petrolina",
                state="PE",
            )
        )

        cls.application = SimpleNamespace(
            municipality=cls.municipality,
        )

    def validate(self, rows):
        report = {
            "errors": [],
            "warnings": [],
        }

        validate_simplified_business_rules(
            rows,
            self.application,
            report,
            check_database=True,
        )

        return report

    def test_inep_from_another_municipality_is_rejected(
        self,
    ):
        School.objects.create(
            municipality=self.other_municipality,
            name="Escola de Petrolina",
            inep_code="26037289",
        )

        report = self.validate([
            student_row(
                "Santa Maria da Boa Vista",
                "PE",
            ),
        ])

        self.assertTrue(
            any(
                "já pertence à escola"
                in item["message"]
                for item in report["errors"]
            )
        )

    def test_local_inep_with_different_name_is_rejected(
        self,
    ):
        School.objects.create(
            municipality=self.municipality,
            name="Escola Municipal Existente",
            inep_code="26037289",
        )

        report = self.validate([
            student_row(
                "Santa Maria da Boa Vista",
                "PE",
                school_name=(
                    "Escola Municipal Horizonte"
                ),
            ),
        ])

        self.assertTrue(
            any(
                "já está associado à escola"
                in item["message"]
                for item in report["errors"]
            )
        )

    def test_existing_name_with_different_inep_is_rejected(
        self,
    ):
        School.objects.create(
            municipality=self.municipality,
            name="Escola Municipal Horizonte",
            inep_code="26000001",
        )

        report = self.validate([
            student_row(
                "Santa Maria da Boa Vista",
                "PE",
                inep_code="26037289",
            ),
        ])

        self.assertTrue(
            any(
                "já está cadastrada com o código INEP"
                in item["message"]
                for item in report["errors"]
            )
        )

    def test_matching_existing_school_is_accepted(
        self,
    ):
        School.objects.create(
            municipality=self.municipality,
            name="Escola Municipal Horizonte",
            inep_code="26037289",
        )

        report = self.validate([
            student_row(
                "Santa Maria da Boa Vista",
                "PE",
            ),
        ])

        self.assertEqual(
            report["errors"],
            [],
        )

    def test_new_school_is_accepted(self):
        report = self.validate([
            student_row(
                "Santa Maria da Boa Vista",
                "PE",
            ),
        ])

        self.assertEqual(
            report["errors"],
            [],
        )