from collections import Counter

from django.core.exceptions import ValidationError

from .import_contract import (
    normalize_grade_code,
    normalize_inep_code,
    normalize_machine_name,
    normalize_postal_code,
    normalize_registration,
    normalize_school_name,
    normalize_school_type,
    normalize_shift,
    normalize_spaces,
    normalize_state,
    normalize_student_name,
)


SIMPLIFIED_REQUIRED_HEADERS = {
    "escola",
    "codigo_inep",
    "municipio",
    "estado",
    "turma",
    "serie",
    "turno",
    "ano_letivo",
    "nome_aluno",
}

SIMPLIFIED_OPTIONAL_HEADERS = {
    "endereco",
    "cep",
    "tipo",
    "matricula",
}

SIMPLIFIED_SUPPORTED_HEADERS = (
    SIMPLIFIED_REQUIRED_HEADERS
    | SIMPLIFIED_OPTIONAL_HEADERS
)

SIMPLIFIED_SIGNATURE = {
    "escola",
    "codigo_inep",
    "turma",
    "serie",
    "nome_aluno",
}


def get_simplified_headers(sheet):
    return [
        normalize_machine_name(cell.value)
        for cell in sheet[1]
        if normalize_machine_name(cell.value)
    ]


def is_simplified_sheet(sheet):
    headers = set(
        get_simplified_headers(sheet)
    )

    return SIMPLIFIED_SIGNATURE.issubset(
        headers
    )


def validate_simplified_headers(sheet):
    headers = get_simplified_headers(sheet)
    counter = Counter(headers)

    duplicated = sorted(
        header
        for header, count in counter.items()
        if count > 1
    )

    if duplicated:
        formatted = ", ".join(duplicated)

        raise ValidationError(
            (
                "A planilha possui cabeçalhos "
                f"duplicados: {formatted}."
            )
        )

    missing = sorted(
        SIMPLIFIED_REQUIRED_HEADERS
        - set(headers)
    )

    if missing:
        formatted = ", ".join(missing)

        raise ValidationError(
            (
                "A planilha simplificada não possui "
                f"as colunas obrigatórias: {formatted}."
            )
        )

    return headers


def normalize_academic_year(value):
    value = normalize_spaces(value)

    if not value:
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def read_simplified_rows(sheet):
    indexed_headers = [
        (
            index,
            normalize_machine_name(
                cell.value
            ),
        )
        for index, cell in enumerate(sheet[1])
        if normalize_machine_name(cell.value)
    ]

    validate_simplified_headers(sheet)

    rows = []

    for row_number, values in enumerate(
        sheet.iter_rows(
            min_row=2,
            values_only=True,
        ),
        start=2,
    ):
        raw_row = {
            header: (
                values[index]
                if index < len(values)
                else None
            )
            for index, header in indexed_headers
        }

        if not any(
            value not in (None, "")
            for value in raw_row.values()
        ):
            continue

        row = {
            "_row": row_number,
            "escola": normalize_school_name(
                raw_row.get("escola")
            ),
            "codigo_inep": normalize_inep_code(
                raw_row.get("codigo_inep")
            ),
            "endereco": normalize_spaces(
                raw_row.get("endereco")
            ),
            "cep": normalize_postal_code(
                raw_row.get("cep")
            ),
            "municipio": normalize_spaces(
                raw_row.get("municipio")
            ),
            "estado": normalize_state(
                raw_row.get("estado")
            ),
            "tipo": normalize_school_type(
                raw_row.get("tipo")
            ),
            "turma": normalize_spaces(
                raw_row.get("turma")
            ),
            "serie": normalize_grade_code(
                raw_row.get("serie")
            ),
            "turno": normalize_shift(
                raw_row.get("turno")
            ),
            "ano_letivo": (
                normalize_academic_year(
                    raw_row.get("ano_letivo")
                )
            ),
            "matricula": normalize_registration(
                raw_row.get("matricula")
            ),
            "nome_aluno": normalize_student_name(
                raw_row.get("nome_aluno")
            ),
        }

        rows.append(row)

    return rows