from django.test import SimpleTestCase

from data_portal.simplified_converter import (
    build_registration_code,
    build_stable_code,
    convert_simplified_rows,
    normalize_subject_codes,
)


def student_row(
    row_number,
    name,
    registration="",
):
    return {
        "_row": row_number,
        "escola": (
            "Escola Municipal Horizonte"
        ),
        "codigo_inep": "26037289",
        "endereco": "Rua Exemplo, 100",
        "cep": "56380000",
        "municipio": (
            "Santa Maria da Boa Vista"
        ),
        "estado": "PE",
        "tipo": "Urbana",
        "turma": "Única",
        "serie": "EF02",
        "turno": "Manhã",
        "ano_letivo": 2026,
        "matricula": registration,
        "nome_aluno": name,
    }


class SimplifiedConverterTest(
    SimpleTestCase
):
    def test_stable_code_is_deterministic(self):
        first = build_stable_code(
            "TESTE",
            "Escola Horizonte",
            "Turma A",
        )
        second = build_stable_code(
            "TESTE",
            "Escola Horizonte",
            "Turma A",
        )

        self.assertEqual(
            first,
            second,
        )

    def test_stable_code_ignores_spacing(self):
        first = build_stable_code(
            "TESTE",
            "Escola  Horizonte",
        )
        second = build_stable_code(
            "TESTE",
            "Escola Horizonte",
        )

        self.assertEqual(
            first,
            second,
        )

    def test_subject_codes_are_normalized(self):
        self.assertEqual(
            normalize_subject_codes([
                "mat",
                " PORT ",
                "MAT",
            ]),
            "MAT;PORT",
        )

    def test_converts_two_students(self):
        rows = [
            student_row(
                2,
                "Ana Beatriz Silva",
            ),
            student_row(
                3,
                "Carlos Eduardo Lima",
            ),
        ]

        converted = convert_simplified_rows(
            rows,
            ["PORT", "MAT"],
        )

        self.assertEqual(
            len(converted["schools"]),
            1,
        )
        self.assertEqual(
            len(converted["classrooms"]),
            1,
        )
        self.assertEqual(
            len(converted["students"]),
            2,
        )

    def test_repeated_school_is_consolidated(self):
        rows = [
            student_row(
                2,
                "Ana Beatriz Silva",
            ),
            student_row(
                3,
                "Carlos Eduardo Lima",
            ),
        ]

        converted = convert_simplified_rows(
            rows,
            ["MAT"],
        )

        school = converted[
            "schools"
        ][0]

        self.assertEqual(
            school["codigo_escola"],
            "INEP-26037289",
        )
        self.assertEqual(
            school["nome_escola"],
            "Escola Municipal Horizonte",
        )

    def test_repeated_classroom_is_consolidated(
        self,
    ):
        rows = [
            student_row(
                2,
                "Ana Beatriz Silva",
            ),
            student_row(
                3,
                "Carlos Eduardo Lima",
            ),
        ]

        converted = convert_simplified_rows(
            rows,
            ["MAT"],
        )

        classroom = converted[
            "classrooms"
        ][0]

        self.assertEqual(
            classroom["codigo_serie"],
            "EF02",
        )
        self.assertEqual(
            classroom["turno"],
            "Manhã",
        )
        self.assertEqual(
            classroom["disciplinas"],
            "MAT",
        )

    def test_preserves_existing_registration(self):
        row = student_row(
            2,
            "Ana Beatriz Silva",
            registration="0001542",
        )

        converted = convert_simplified_rows(
            [row],
            ["MAT"],
        )

        student = converted[
            "students"
        ][0]

        self.assertEqual(
            student["matricula"],
            "0001542",
        )
        self.assertFalse(
            student["_matricula_gerada"]
        )

    def test_generates_missing_registration(self):
        row = student_row(
            2,
            "Ana Beatriz Silva",
        )

        converted = convert_simplified_rows(
            [row],
            ["MAT"],
        )

        student = converted[
            "students"
        ][0]

        self.assertTrue(
            student["matricula"].startswith(
                "AUTO-"
            )
        )
        self.assertTrue(
            student["_matricula_gerada"]
        )

    def test_generated_registration_is_stable(self):
        row = student_row(
            2,
            "Ana Beatriz Silva",
        )

        first = convert_simplified_rows(
            [row],
            ["MAT"],
        )
        second = convert_simplified_rows(
            [row],
            ["MAT"],
        )

        self.assertEqual(
            first["students"][0][
                "matricula"
            ],
            second["students"][0][
                "matricula"
            ],
        )

    def test_same_name_in_same_class_collides(self):
        row = student_row(
            2,
            "Ana Beatriz Silva",
        )

        school_code = "INEP-26037289"
        classroom_code = "TUR-TESTE"

        first, _ = build_registration_code(
            school_code,
            classroom_code,
            row,
        )
        second, _ = build_registration_code(
            school_code,
            classroom_code,
            row,
        )

        self.assertEqual(
            first,
            second,
        )

    def test_different_classes_generate_different_codes(
        self,
    ):
        row = student_row(
            2,
            "Ana Beatriz Silva",
        )

        first, _ = build_registration_code(
            "INEP-26037289",
            "TURMA-A",
            row,
        )
        second, _ = build_registration_code(
            "INEP-26037289",
            "TURMA-B",
            row,
        )

        self.assertNotEqual(
            first,
            second,
        )