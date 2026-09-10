from io import BytesIO

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.worksheet.datavalidation import (
    DataValidation,
)


DARK_RED = "991B1B"
RED = "C81E1E"
LIGHT_RED = "FDECEC"
LIGHT_GOLD = "FFF4D6"
DARK_TEXT = "3F1D1D"
WHITE = "FFFFFF"
GRAY = "6B7280"

HEADER_FILL = PatternFill(
    "solid",
    fgColor=DARK_RED,
)
TITLE_FILL = PatternFill(
    "solid",
    fgColor=RED,
)
REQUIRED_FILL = PatternFill(
    "solid",
    fgColor=LIGHT_RED,
)
OPTIONAL_FILL = PatternFill(
    "solid",
    fgColor=LIGHT_GOLD,
)
WHITE_FONT = Font(
    color=WHITE,
    bold=True,
)
THIN_RED = Side(
    style="thin",
    color="E8B4B4",
)


HEADERS = [
    "escola",
    "codigo_inep",
    "endereco",
    "cep",
    "municipio",
    "estado",
    "tipo",
    "turma",
    "serie",
    "turno",
    "ano_letivo",
    "matricula",
    "nome_aluno",
]

REQUIRED_HEADERS = {
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

COLUMN_WIDTHS = {
    "A": 42,
    "B": 18,
    "C": 42,
    "D": 16,
    "E": 30,
    "F": 12,
    "G": 16,
    "H": 18,
    "I": 18,
    "J": 18,
    "K": 18,
    "L": 22,
    "M": 42,
}

COMMENTS = {
    "escola": (
        "Nome oficial da escola."
    ),
    "codigo_inep": (
        "Código INEP da escola. Se não estiver "
        "disponível, deixe a célula vazia."
    ),
    "endereco": (
        "Endereço institucional da escola."
    ),
    "cep": (
        "CEP da escola, com ou sem pontuação."
    ),
    "municipio": (
        "Município da aplicação. Deve corresponder "
        "ao município autorizado no portal."
    ),
    "estado": (
        "Sigla do estado, por exemplo: PE ou CE."
    ),
    "tipo": (
        "Localização da escola: Urbana ou Rural."
    ),
    "turma": (
        "Identificação da turma. Exemplos: A, B, "
        "Única ou 901."
    ),
    "serie": (
        "Série/ano autorizado para esta avaliação."
    ),
    "turno": (
        "Turno da turma: Manhã, Tarde, Noite "
        "ou Integral."
    ),
    "ano_letivo": (
        "Ano letivo da avaliação."
    ),
    "matricula": (
        "Matrícula do aluno. É opcional. Quando "
        "vazia, o sistema gera um código interno."
    ),
    "nome_aluno": (
        "Nome completo do aluno, sem abreviações."
    ),
}


def get_subject_codes(assessment):
    subject_codes = list(
        assessment.components.filter(
            is_active=True,
        ).values_list(
            "subject__code",
            flat=True,
        )
    )

    if (
        not subject_codes
        and assessment.subject_id
    ):
        subject_codes = [
            assessment.subject.code
        ]

    return sorted(set(subject_codes))


def configure_instructions(
    sheet,
    portal,
):
    application = portal.application
    assessment = application.assessment

    sheet.sheet_view.showGridLines = False

    sheet.merge_cells("A1:F2")
    sheet["A1"] = (
        "DINÂMICA SIMULADOS — CADASTRO DE ALUNOS"
    )
    sheet["A1"].fill = TITLE_FILL
    sheet["A1"].font = Font(
        color=WHITE,
        bold=True,
        size=18,
    )
    sheet["A1"].alignment = Alignment(
        horizontal="center",
        vertical="center",
    )

    information = [
        ("Aplicação", application.title),
        ("Código", application.code),
        ("Município", application.municipality.name),
        ("Estado", application.municipality.state),
        ("Avaliação", assessment.title),
        ("Ano letivo", assessment.academic_year.year),
        (
            "Séries autorizadas",
            ", ".join(
                assessment.grades.filter(
                    is_active=True,
                ).values_list(
                    "name",
                    flat=True,
                )
            ),
        ),
        (
            "Disciplinas",
            ", ".join(
                get_subject_codes(assessment)
            ),
        ),
    ]

    start_row = 4

    for index, (label, value) in enumerate(
        information,
        start=start_row,
    ):
        sheet.cell(
            row=index,
            column=1,
            value=label,
        )
        sheet.cell(
            row=index,
            column=2,
            value=value,
        )

        sheet.cell(
            row=index,
            column=1,
        ).font = Font(
            bold=True,
            color=DARK_RED,
        )

    orientation_row = start_row + len(
        information
    ) + 2

    sheet.cell(
        row=orientation_row,
        column=1,
        value="COMO PREENCHER",
    )
    sheet.cell(
        row=orientation_row,
        column=1,
    ).fill = HEADER_FILL
    sheet.cell(
        row=orientation_row,
        column=1,
    ).font = WHITE_FONT

    guidance = [
        (
            "Utilize somente a aba ALUNOS para "
            "informar os estudantes."
        ),
        (
            "Cada linha representa um aluno."
        ),
        (
            "Repita os dados da escola e da turma "
            "em todas as linhas necessárias."
        ),
        (
            "Não altere o nome da aba nem os "
            "cabeçalhos das colunas."
        ),
        (
            "Os campos em vermelho-claro são "
            "obrigatórios."
        ),
        (
            "A matrícula é opcional. Quando não "
            "informada, o sistema cria um código."
        ),
        (
            "O município e o estado devem ser os "
            "mesmos apresentados nesta página."
        ),
        (
            "Não informe CPF, telefone, endereço "
            "residencial ou documentos do aluno."
        ),
        (
            "Use uma linha para cada aluno e não "
            "deixe linhas vazias entre registros."
        ),
        (
            "Depois de preencher, envie o mesmo "
            "arquivo pelo portal seguro."
        ),
    ]

    for number, text in enumerate(
        guidance,
        start=1,
    ):
        row = orientation_row + number

        sheet.cell(
            row=row,
            column=1,
            value=number,
        )
        sheet.cell(
            row=row,
            column=2,
            value=text,
        )

    example_row = (
        orientation_row
        + len(guidance)
        + 2
    )

    sheet.cell(
        row=example_row,
        column=1,
        value="EXEMPLO",
    )
    sheet.cell(
        row=example_row,
        column=1,
    ).fill = OPTIONAL_FILL
    sheet.cell(
        row=example_row,
        column=1,
    ).font = Font(
        bold=True,
        color=DARK_TEXT,
    )

    sheet.cell(
        row=example_row + 1,
        column=2,
        value=(
            "Escola Municipal Horizonte | "
            "26037289 | Turma A | 2º ano | "
            "Manhã | Ana Beatriz Silva"
        ),
    )

    sheet.column_dimensions["A"].width = 24
    sheet.column_dimensions["B"].width = 82

    for row in range(
        1,
        example_row + 2,
    ):
        sheet.row_dimensions[row].height = 24


def configure_students_sheet(
    sheet,
    portal,
):
    application = portal.application
    assessment = application.assessment

    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:M1001"

    for column, header in enumerate(
        HEADERS,
        start=1,
    ):
        cell = sheet.cell(
            row=1,
            column=column,
            value=header,
        )
        cell.fill = HEADER_FILL
        cell.font = WHITE_FONT
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )
        cell.border = Border(
            bottom=THIN_RED,
        )
        cell.comment = Comment(
            COMMENTS[header],
            "Editora Dinâmica",
        )

    sheet.row_dimensions[1].height = 34

    for column, width in COLUMN_WIDTHS.items():
        sheet.column_dimensions[
            column
        ].width = width

    for row in range(2, 1002):
        for column, header in enumerate(
            HEADERS,
            start=1,
        ):
            cell = sheet.cell(
                row=row,
                column=column,
            )

            if header in REQUIRED_HEADERS:
                cell.fill = REQUIRED_FILL
            else:
                cell.fill = OPTIONAL_FILL

            cell.border = Border(
                bottom=Side(
                    style="hair",
                    color="E5E7EB",
                ),
            )
            cell.alignment = Alignment(
                vertical="top",
                wrap_text=True,
            )

        sheet.cell(
            row=row,
            column=2,
        ).number_format = "@"
        sheet.cell(
            row=row,
            column=4,
        ).number_format = "@"
        sheet.cell(
            row=row,
            column=12,
        ).number_format = "@"

    grade_count = assessment.grades.filter(
        is_active=True,
    ).count()

    if grade_count:
        grade_validation = DataValidation(
            type="list",
            formula1=(
                f"'LISTAS'!$A$2:$A$"
                f"{grade_count + 1}"
            ),
            allow_blank=False,
        )
        grade_validation.error = (
            "Selecione uma série autorizada."
        )
        grade_validation.errorTitle = (
            "Série inválida"
        )
        grade_validation.prompt = (
            "Selecione a série/ano."
        )
        grade_validation.promptTitle = (
            "Série"
        )
        grade_validation.showErrorMessage = True
        grade_validation.showInputMessage = True

        sheet.add_data_validation(
            grade_validation
        )
        grade_validation.add(
            "I2:I1001"
        )

    shift_validation = DataValidation(
        type="list",
        formula1="'LISTAS'!$B$2:$B$5",
        allow_blank=False,
    )
    shift_validation.error = (
        "Selecione um turno válido."
    )
    shift_validation.errorTitle = (
        "Turno inválido"
    )
    shift_validation.showErrorMessage = True

    sheet.add_data_validation(
        shift_validation
    )
    shift_validation.add(
        "J2:J1001"
    )

    type_validation = DataValidation(
        type="list",
        formula1="'LISTAS'!$C$2:$C$3",
        allow_blank=True,
    )
    type_validation.error = (
        "Selecione Urbana ou Rural."
    )
    type_validation.errorTitle = (
        "Tipo inválido"
    )
    type_validation.showErrorMessage = True

    sheet.add_data_validation(
        type_validation
    )
    type_validation.add(
        "G2:G1001"
    )

    state_validation = DataValidation(
        type="list",
        formula1="'LISTAS'!$D$2",
        allow_blank=False,
    )
    state_validation.error = (
        "Use o estado autorizado para a aplicação."
    )
    state_validation.errorTitle = (
        "Estado inválido"
    )
    state_validation.showErrorMessage = True

    sheet.add_data_validation(
        state_validation
    )
    state_validation.add(
        "F2:F1001"
    )

    year_validation = DataValidation(
        type="whole",
        operator="equal",
        formula1=str(
            assessment.academic_year.year
        ),
        allow_blank=False,
    )
    year_validation.error = (
        "Informe o ano letivo da avaliação."
    )
    year_validation.errorTitle = (
        "Ano letivo inválido"
    )
    year_validation.showErrorMessage = True

    sheet.add_data_validation(
        year_validation
    )
    year_validation.add(
        "K2:K1001"
    )


def configure_lists_sheet(
    sheet,
    portal,
):
    application = portal.application
    assessment = application.assessment

    sheet.append([
        "SERIES",
        "TURNOS",
        "TIPOS",
        "ESTADO",
        "MUNICIPIO",
        "DISCIPLINAS",
    ])

    grades = list(
        assessment.grades.filter(
            is_active=True,
        ).values_list(
            "name",
            flat=True,
        )
    )
    shifts = [
        "Manhã",
        "Tarde",
        "Noite",
        "Integral",
    ]
    school_types = [
        "Urbana",
        "Rural",
    ]
    subject_codes = get_subject_codes(
        assessment
    )

    maximum = max(
        len(grades),
        len(shifts),
        len(school_types),
        len(subject_codes),
        1,
    )

    for index in range(maximum):
        sheet.append([
            (
                grades[index]
                if index < len(grades)
                else None
            ),
            (
                shifts[index]
                if index < len(shifts)
                else None
            ),
            (
                school_types[index]
                if index < len(school_types)
                else None
            ),
            (
                application.municipality.state
                if index == 0
                else None
            ),
            (
                application.municipality.name
                if index == 0
                else None
            ),
            (
                subject_codes[index]
                if index < len(subject_codes)
                else None
            ),
        ])

    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = WHITE_FONT

    sheet.sheet_state = "hidden"


def build_student_import_workbook(portal):
    workbook = Workbook()

    instructions = workbook.active
    instructions.title = "INSTRUCOES"

    students = workbook.create_sheet(
        "ALUNOS"
    )
    lists = workbook.create_sheet(
        "LISTAS"
    )

    configure_instructions(
        instructions,
        portal,
    )
    configure_students_sheet(
        students,
        portal,
    )
    configure_lists_sheet(
        lists,
        portal,
    )

    workbook.active = 1

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return output