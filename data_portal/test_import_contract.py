from decimal import Decimal

from django.test import SimpleTestCase

from data_portal.import_contract import (
    normalize_grade_code,
    normalize_identifier,
    normalize_inep_code,
    normalize_machine_name,
    normalize_postal_code,
    normalize_school_name,
    normalize_school_type,
    normalize_shift,
    normalize_spaces,
    normalize_state,
    normalize_student_name,
)


class ImportContractTest(SimpleTestCase):
    def test_normalize_spaces(self):
        self.assertEqual(
            normalize_spaces(
                "  Escola   Municipal  Horizonte  "
            ),
            "Escola Municipal Horizonte",
        )

    def test_normalize_machine_name(self):
        self.assertEqual(
            normalize_machine_name(
                "Código INEP*"
            ),
            "codigo_inep",
        )

    def test_integer_identifier(self):
        self.assertEqual(
            normalize_identifier(26037289),
            "26037289",
        )

    def test_float_identifier(self):
        self.assertEqual(
            normalize_identifier(26037289.0),
            "26037289",
        )

    def test_decimal_identifier(self):
        self.assertEqual(
            normalize_identifier(
                Decimal("26037289.00")
            ),
            "26037289",
        )

    def test_inep_code(self):
        self.assertEqual(
            normalize_inep_code(
                " 26037289 "
            ),
            "26037289",
        )

    def test_postal_code(self):
        self.assertEqual(
            normalize_postal_code(
                "56.380-000"
            ),
            "56380000",
        )

    def test_grade_as_number(self):
        self.assertEqual(
            normalize_grade_code(2),
            "EF02",
        )

    def test_grade_as_name(self):
        self.assertEqual(
            normalize_grade_code(
                "2º ano"
            ),
            "EF02",
        )

    def test_grade_with_degree_symbol(self):
        self.assertEqual(
            normalize_grade_code(
                "5° ano"
            ),
            "EF05",
        )

    def test_grade_with_feminine_ordinal(self):
        self.assertEqual(
            normalize_grade_code(
                "9ª ano"
            ),
            "EF09",
        )

    def test_grade_without_ordinal(self):
        self.assertEqual(
            normalize_grade_code(
                "2 ano"
            ),
            "EF02",
        )

    def test_grade_as_code(self):
        self.assertEqual(
            normalize_grade_code(
                "ef09"
            ),
            "EF09",
        )

    def test_invalid_grade(self):
        self.assertEqual(
            normalize_grade_code(
                "3º ano"
            ),
            "",
        )

    def test_morning_shift(self):
        self.assertEqual(
            normalize_shift(
                "Matutino"
            ),
            "Manhã",
        )

    def test_afternoon_shift(self):
        self.assertEqual(
            normalize_shift(
                "vespertino"
            ),
            "Tarde",
        )

    def test_invalid_shift(self):
        self.assertEqual(
            normalize_shift(""),
            "",
        )

    def test_school_type(self):
        self.assertEqual(
            normalize_school_type(
                "urbano"
            ),
            "Urbana",
        )

    def test_state_name(self):
        self.assertEqual(
            normalize_state(
                "Pernambuco"
            ),
            "PE",
        )

    def test_school_name_removes_extra_spaces(self):
        self.assertEqual(
            normalize_school_name(
                "  Escola   Municipal Horizonte "
            ),
            "Escola Municipal Horizonte",
        )

    def test_student_name_removes_extra_spaces(self):
        self.assertEqual(
            normalize_student_name(
                "  Ana   Beatriz da Silva "
            ),
            "Ana Beatriz da Silva",
        )