import hashlib

from .import_contract import (
    normalize_machine_name,
    normalize_spaces,
)


def build_stable_code(prefix, *values):
    content = "|".join(
        normalize_machine_name(value)
        for value in values
    )

    digest = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()[:16].upper()

    return f"{prefix}-{digest}"


def build_school_code(row):
    inep_code = row.get(
        "codigo_inep",
        "",
    )

    if inep_code:
        return f"INEP-{inep_code}"

    return build_stable_code(
        "ESC",
        row.get("escola"),
        row.get("municipio"),
        row.get("estado"),
    )


def build_classroom_code(
    school_code,
    row,
):
    return build_stable_code(
        "TUR",
        school_code,
        row.get("ano_letivo"),
        row.get("serie"),
        row.get("turma"),
        row.get("turno"),
    )


def build_registration_code(
    school_code,
    classroom_code,
    row,
):
    registration = row.get(
        "matricula",
        "",
    )

    if registration:
        return registration, False

    generated = build_stable_code(
        "AUTO",
        school_code,
        classroom_code,
        row.get("nome_aluno"),
    )

    return generated, True


def normalize_subject_codes(
    subject_codes,
):
    return ";".join(
        sorted({
            normalize_spaces(code).upper()
            for code in subject_codes
            if normalize_spaces(code)
        })
    )


def convert_simplified_rows(
    rows,
    subject_codes,
):
    subjects = normalize_subject_codes(
        subject_codes
    )

    schools_by_code = {}
    classrooms_by_code = {}
    students = []

    for row in rows:
        school_code = build_school_code(
            row
        )

        if school_code not in schools_by_code:
            schools_by_code[school_code] = {
                "_row": row["_row"],
                "codigo_escola": school_code,
                "codigo_inep": row.get(
                    "codigo_inep",
                    "",
                ),
                "nome_escola": row.get(
                    "escola",
                    "",
                ),
                "endereco": row.get(
                    "endereco",
                    "",
                ),
                "cep": row.get(
                    "cep",
                    "",
                ),
                "municipio": row.get(
                    "municipio",
                    "",
                ),
                "estado": row.get(
                    "estado",
                    "",
                ),
                "tipo": row.get(
                    "tipo",
                    "",
                ),
            }

        classroom_code = (
            build_classroom_code(
                school_code,
                row,
            )
        )

        if (
            classroom_code
            not in classrooms_by_code
        ):
            classrooms_by_code[
                classroom_code
            ] = {
                "_row": row["_row"],
                "codigo_turma": (
                    classroom_code
                ),
                "codigo_escola": school_code,
                "ano_letivo": row.get(
                    "ano_letivo"
                ),
                "codigo_serie": row.get(
                    "serie",
                    "",
                ),
                "nome_turma": row.get(
                    "turma",
                    "",
                ),
                "turno": row.get(
                    "turno",
                    "",
                ),
                "sala": "",
                "disciplinas": subjects,
            }

        (
            registration,
            generated_registration,
        ) = build_registration_code(
            school_code,
            classroom_code,
            row,
        )

        students.append({
            "_row": row["_row"],
            "codigo_escola": school_code,
            "codigo_turma": classroom_code,
            "matricula": registration,
            "nome_completo": row.get(
                "nome_aluno",
                "",
            ),
            "data_nascimento": None,
            "necessidade_atendimento": "",
            "observacao_aplicacao": "",
            "_matricula_gerada": (
                generated_registration
            ),
        })

    return {
        "schools": list(
            schools_by_code.values()
        ),
        "classrooms": list(
            classrooms_by_code.values()
        ),
        "students": students,
    }