from institutions.models import School

from .import_contract import (
    normalize_machine_name,
    normalize_spaces,
)


def add_issue(
    report,
    level,
    row,
    message,
):
    report[level].append({
        "sheet": "ALUNOS",
        "row": row,
        "message": message,
    })


def comparable(value):
    return normalize_machine_name(
        normalize_spaces(value)
    )


def validate_required_values(
    row,
    report,
):
    row_number = row["_row"]

    required_fields = {
        "escola": "Escola",
        "municipio": "Município",
        "estado": "Estado",
        "turma": "Turma",
        "serie": "Série",
        "turno": "Turno",
        "ano_letivo": "Ano letivo",
        "nome_aluno": "Nome do aluno",
    }

    for field, label in required_fields.items():
        if row.get(field) in (None, ""):
            add_issue(
                report,
                "errors",
                row_number,
                f"{label} é obrigatório.",
            )


def validate_application_location(
    row,
    application,
    report,
):
    row_number = row["_row"]
    municipality = application.municipality

    informed_city = comparable(
        row.get("municipio")
    )
    expected_city = comparable(
        municipality.name
    )

    if (
        informed_city
        and informed_city != expected_city
    ):
        add_issue(
            report,
            "errors",
            row_number,
            (
                "O município informado "
                f"({row.get('municipio')}) não corresponde "
                f"ao município da aplicação "
                f"({municipality.name})."
            ),
        )

    informed_state = normalize_spaces(
        row.get("estado")
    ).upper()
    expected_state = normalize_spaces(
        municipality.state
    ).upper()

    if (
        informed_state
        and informed_state != expected_state
    ):
        add_issue(
            report,
            "errors",
            row_number,
            (
                "O estado informado "
                f"({informed_state}) não corresponde "
                f"ao estado da aplicação "
                f"({expected_state})."
            ),
        )


def validate_school_consistency(
    rows,
    report,
):
    schools_by_name = {}
    names_by_inep = {}

    compared_fields = {
        "codigo_inep": "código INEP",
        "endereco": "endereço",
        "cep": "CEP",
        "tipo": "tipo da escola",
        "municipio": "município",
        "estado": "estado",
    }

    for row in rows:
        row_number = row["_row"]
        school_name = comparable(
            row.get("escola")
        )
        inep_code = normalize_spaces(
            row.get("codigo_inep")
        )

        if not school_name:
            continue

        previous = schools_by_name.get(
            school_name
        )

        if previous is None:
            schools_by_name[school_name] = row
        else:
            for field, label in compared_fields.items():
                current_value = comparable(
                    row.get(field)
                )
                previous_value = comparable(
                    previous.get(field)
                )

                if (
                    current_value
                    and previous_value
                    and current_value
                    != previous_value
                ):
                    add_issue(
                        report,
                        "errors",
                        row_number,
                        (
                            f"A escola {row.get('escola')} "
                            f"possui {label} diferente da "
                            f"linha {previous['_row']}."
                        ),
                    )

        if not inep_code:
            continue

        previous_name = names_by_inep.get(
            inep_code
        )

        if (
            previous_name
            and previous_name != school_name
        ):
            add_issue(
                report,
                "errors",
                row_number,
                (
                    f"O código INEP {inep_code} foi usado "
                    "para escolas com nomes diferentes."
                ),
            )
        else:
            names_by_inep[inep_code] = (
                school_name
            )


def validate_classroom_consistency(
    rows,
    report,
):
    classrooms = {}

    for row in rows:
        school_key = (
            row.get("codigo_inep")
            or comparable(row.get("escola"))
        )
        classroom_name = comparable(
            row.get("turma")
        )

        if not school_key or not classroom_name:
            continue

        key = (
            school_key,
            classroom_name,
        )
        configuration = (
            row.get("serie"),
            row.get("turno"),
            row.get("ano_letivo"),
        )

        previous = classrooms.get(key)

        if previous is None:
            classrooms[key] = {
                "configuration": configuration,
                "row": row["_row"],
            }
            continue

        if (
            previous["configuration"]
            != configuration
        ):
            add_issue(
                report,
                "errors",
                row["_row"],
                (
                    f"A turma {row.get('turma')} possui "
                    "série, turno ou ano letivo diferente "
                    f"da linha {previous['row']}."
                ),
            )


def validate_student_duplicates(
    rows,
    report,
):
    students = {}

    for row in rows:
        school_key = (
            row.get("codigo_inep")
            or comparable(row.get("escola"))
        )
        classroom_key = comparable(
            row.get("turma")
        )
        student_name = comparable(
            row.get("nome_aluno")
        )

        if not all([
            school_key,
            classroom_key,
            student_name,
        ]):
            continue

        key = (
            school_key,
            classroom_key,
            student_name,
        )

        previous_row = students.get(key)

        if previous_row is not None:
            add_issue(
                report,
                "errors",
                row["_row"],
                (
                    f"O aluno {row.get('nome_aluno')} "
                    "aparece mais de uma vez na mesma "
                    f"turma. Primeira ocorrência: linha "
                    f"{previous_row}."
                ),
            )
        else:
            students[key] = row["_row"]


def validate_database_school_conflicts(
    rows,
    application,
    report,
):
    municipality = application.municipality
    checked_inep_codes = set()
    checked_names = set()

    for row in rows:
        row_number = row["_row"]
        school_name = normalize_spaces(
            row.get("escola")
        )
        school_name_key = comparable(
            school_name
        )
        inep_code = normalize_spaces(
            row.get("codigo_inep")
        )

        if (
            inep_code
            and inep_code not in checked_inep_codes
        ):
            checked_inep_codes.add(
                inep_code
            )

            outside_school = (
                School.objects
                .filter(inep_code=inep_code)
                .exclude(
                    municipality_id=municipality.pk
                )
                .first()
            )

            if outside_school:
                add_issue(
                    report,
                    "errors",
                    row_number,
                    (
                        f"O código INEP {inep_code} já "
                        "pertence à escola "
                        f"{outside_school.name}, no município "
                        f"{outside_school.municipality}."
                    ),
                )

            local_school = (
                School.objects
                .filter(
                    municipality=municipality,
                    inep_code=inep_code,
                )
                .first()
            )

            if (
                local_school
                and comparable(local_school.name)
                != school_name_key
            ):
                add_issue(
                    report,
                    "errors",
                    row_number,
                    (
                        f"O código INEP {inep_code} já está "
                        f"associado à escola "
                        f"{local_school.name}."
                    ),
                )

        if (
            not school_name_key
            or school_name_key in checked_names
        ):
            continue

        checked_names.add(
            school_name_key
        )

        local_schools = School.objects.filter(
            municipality=municipality,
        )

        existing_by_name = next(
            (
                school
                for school in local_schools
                if comparable(school.name)
                == school_name_key
            ),
            None,
        )

        if (
            existing_by_name
            and inep_code
            and existing_by_name.inep_code
            and existing_by_name.inep_code
            != inep_code
        ):
            add_issue(
                report,
                "errors",
                row_number,
                (
                    f"A escola {school_name} já está "
                    "cadastrada com o código INEP "
                    f"{existing_by_name.inep_code}."
                ),
            )


def validate_simplified_business_rules(
    rows,
    application,
    report,
    check_database=True,
):
    for row in rows:
        validate_required_values(
            row,
            report,
        )
        validate_application_location(
            row,
            application,
            report,
        )

    validate_school_consistency(
        rows,
        report,
    )
    validate_classroom_consistency(
        rows,
        report,
    )
    validate_student_duplicates(
        rows,
        report,
    )

    if check_database:
        validate_database_school_conflicts(
            rows,
            application,
            report,
        )

    return report