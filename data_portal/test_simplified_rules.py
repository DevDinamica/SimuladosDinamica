from types import SimpleNamespace

from django.test import SimpleTestCase

from data_portal.simplified_rules import (
    validate_simplified_business_rules,
)


def application():
    municipality = SimpleNamespace(
        name="Santa Maria da Boa Vista",
        state="PE",
    )

    return SimpleNamespace(
        municipality=municipality,
    )


def valid_row(row_number=2):
    return {
        "_row": row_number,
        "escola": "Escola Municipal Horizonte",
        "codigo_inep": "26037289",
        "endereco": "Rua Exemplo, 100",
        "cep": "56380000",
        "municipio": "Santa Maria da Boa Vista",
        "estado": "PE",
        "tipo": "Urbana",
        "turma": "A",
        "serie": "EF02",
        "turno": "Manhã",
        "ano_letivo": 2026,
        "matricula": "",
        "nome_aluno": "Ana Beatriz Silva",
    }


def validate(rows):
    report = {
        "errors": [],
        "warnings": [],
    }

    validate_simplified_business_rules(
        rows,
        application(),
        report,
        check_database=False,
    )

    return report


class SimplifiedBusinessRulesTest(
    SimpleTestCase
):
    def test_valid_row_is_accepted(self):
        report = validate([
            valid_row(),
        ])

        self.assertEqual(
            report["errors"],
            [],
        )

    def test_different_municipality_is_rejected(self):
        row = valid_row()
        row["municipio"] = "Petrolina"

        report = validate([row])

        self.assertTrue(
            any(
                "não corresponde ao município"
                in item["message"]
                for item in report["errors"]
            )
        )

    def test_different_state_is_rejected(self):
        row = valid_row()
        row["estado"] = "CE"

        report = validate([row])

        self.assertTrue(
            any(
                "não corresponde ao estado"
                in item["message"]
                for item in report["errors"]
            )
        )

    def test_missing_shift_is_rejected(self):
        row = valid_row()
        row["turno"] = ""

        report = validate([row])

        self.assertTrue(
            any(
                item["message"]
                == "Turno é obrigatório."
                for item in report["errors"]
            )
        )

    def test_school_with_conflicting_data_is_rejected(
        self,
    ):
        first = valid_row(2)
        second = valid_row(3)
        second["nome_aluno"] = "Carlos Eduardo Lima"
        second["endereco"] = "Avenida Diferente, 200"

        report = validate([
            first,
            second,
        ])

        self.assertTrue(
            any(
                "endereço diferente"
                in item["message"]
                for item in report["errors"]
            )
        )

    def test_same_inep_for_different_schools_is_rejected(
        self,
    ):
        first = valid_row(2)
        second = valid_row(3)
        second["escola"] = "Outra Escola"
        second["nome_aluno"] = "Carlos Eduardo Lima"

        report = validate([
            first,
            second,
        ])

        self.assertTrue(
            any(
                "escolas com nomes diferentes"
                in item["message"]
                for item in report["errors"]
            )
        )

    def test_conflicting_classroom_is_rejected(self):
        first = valid_row(2)
        second = valid_row(3)
        second["nome_aluno"] = "Carlos Eduardo Lima"
        second["turno"] = "Tarde"

        report = validate([
            first,
            second,
        ])

        self.assertTrue(
            any(
                "série, turno ou ano letivo diferente"
                in item["message"]
                for item in report["errors"]
            )
        )

    def test_duplicated_student_is_rejected(self):
        first = valid_row(2)
        second = valid_row(3)

        report = validate([
            first,
            second,
        ])

        self.assertTrue(
            any(
                "aparece mais de uma vez"
                in item["message"]
                for item in report["errors"]
            )
        )

    def test_same_name_in_different_class_is_allowed(
        self,
    ):
        first = valid_row(2)
        second = valid_row(3)
        second["turma"] = "B"

        report = validate([
            first,
            second,
        ])

        self.assertEqual(
            report["errors"],
            [],
        )

    def test_missing_student_name_is_rejected(self):
        row = valid_row()
        row["nome_aluno"] = ""

        report = validate([row])

        self.assertTrue(
            any(
                item["message"]
                == "Nome do aluno é obrigatório."
                for item in report["errors"]
            )
        )