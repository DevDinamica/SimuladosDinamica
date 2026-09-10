import re
import unicodedata
from decimal import Decimal


SIMPLIFIED_SHEET = "ALUNOS"

SIMPLIFIED_HEADERS = {
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
}

SIMPLIFIED_REQUIRED_HEADERS = {
    "escola",
    "codigo_inep",
    "turma",
    "serie",
    "ano_letivo",
    "nome_aluno",
}

GRADE_ALIASES = {
    "2": "EF02",
    "02": "EF02",
    "2 ANO": "EF02",
    "2º ANO": "EF02",
    "2° ANO": "EF02",
    "EF02": "EF02",

    "5": "EF05",
    "05": "EF05",
    "5 ANO": "EF05",
    "5º ANO": "EF05",
    "5° ANO": "EF05",
    "EF05": "EF05",

    "9": "EF09",
    "09": "EF09",
    "9 ANO": "EF09",
    "9º ANO": "EF09",
    "9° ANO": "EF09",
    "EF09": "EF09",
}

SHIFT_ALIASES = {
    "MANHA": "Manhã",
    "MATUTINO": "Manhã",

    "TARDE": "Tarde",
    "VESPERTINO": "Tarde",

    "NOITE": "Noite",
    "NOTURNO": "Noite",

    "INTEGRAL": "Integral",
}

SCHOOL_TYPE_ALIASES = {
    "URBANA": "Urbana",
    "URBANO": "Urbana",
    "RURAL": "Rural",
}


def remove_accents(value):
    value = str(value or "")

    return "".join(
        character
        for character in unicodedata.normalize(
            "NFKD",
            value,
        )
        if not unicodedata.combining(character)
    )


def normalize_spaces(value):
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def normalize_machine_name(value):
    value = remove_accents(
        normalize_spaces(value)
    ).lower()

    value = value.replace("*", "")
    value = re.sub(r"[^a-z0-9]+", "_", value)

    return value.strip("_")


def normalize_identifier(value):
    if value is None:
        return ""

    if isinstance(value, bool):
        return str(value)

    if isinstance(value, int):
        return str(value)

    if isinstance(value, Decimal):
        if value == value.to_integral():
            return str(int(value))

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))

    text = normalize_spaces(value)

    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", maxsplit=1)[0]

    return text


def normalize_grade_code(value):
    identifier = normalize_identifier(value)

    normalized = remove_accents(
        identifier
    ).upper()

    compact = re.sub(
        r"[^A-Z0-9]",
        "",
        normalized,
    )

    grade_variations = {
        "2": "EF02",
        "02": "EF02",
        "2O": "EF02",
        "2A": "EF02",
        "2ANO": "EF02",
        "2OANO": "EF02",
        "2AANO": "EF02",
        "EF02": "EF02",

        "5": "EF05",
        "05": "EF05",
        "5O": "EF05",
        "5A": "EF05",
        "5ANO": "EF05",
        "5OANO": "EF05",
        "5AANO": "EF05",
        "EF05": "EF05",

        "9": "EF09",
        "09": "EF09",
        "9O": "EF09",
        "9A": "EF09",
        "9ANO": "EF09",
        "9OANO": "EF09",
        "9AANO": "EF09",
        "EF09": "EF09",
    }

    return grade_variations.get(
        compact,
        "",
    )


def normalize_shift(value):
    normalized = remove_accents(
        normalize_spaces(value)
    ).upper()

    return SHIFT_ALIASES.get(
        normalized,
        "",
    )


def normalize_school_type(value):
    normalized = remove_accents(
        normalize_spaces(value)
    ).upper()

    return SCHOOL_TYPE_ALIASES.get(
        normalized,
        "",
    )


def normalize_state(value):
    value = normalize_spaces(value)

    aliases = {
        "CE": "CE",
        "CEARA": "CE",
        "PE": "PE",
        "PERNAMBUCO": "PE",
    }

    normalized = remove_accents(value).upper()

    return aliases.get(
        normalized,
        normalized,
    )


def normalize_inep_code(value):
    return normalize_identifier(value)


def normalize_postal_code(value):
    value = normalize_identifier(value)

    return re.sub(
        r"\D",
        "",
        value,
    )


def normalize_registration(value):
    return normalize_identifier(value)


def normalize_student_name(value):
    return normalize_spaces(value)


def normalize_school_name(value):
    return normalize_spaces(value)


def normalize_classroom_name(value):
    return normalize_spaces(value)