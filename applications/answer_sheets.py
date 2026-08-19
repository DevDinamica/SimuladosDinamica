from io import BytesIO
from pathlib import Path

import qrcode
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from reportlab.lib.colors import (
    HexColor,
    black,
    white,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


BLUE = HexColor("#173D7A")
LIGHT_BLUE = HexColor("#EAF1FA")
GOLD = HexColor("#F2A900")
GRAY = HexColor("#64748B")
LIGHT_GRAY = HexColor("#D9E2EF")

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def register_fonts():
    global FONT_REGULAR
    global FONT_BOLD

    regular_path = Path(
        "/usr/share/fonts/truetype/dejavu/"
        "DejaVuSans.ttf"
    )
    bold_path = Path(
        "/usr/share/fonts/truetype/dejavu/"
        "DejaVuSans-Bold.ttf"
    )

    if regular_path.exists():
        pdfmetrics.registerFont(
            TTFont(
                "DejaVu",
                str(regular_path),
            )
        )
        FONT_REGULAR = "DejaVu"

    if bold_path.exists():
        pdfmetrics.registerFont(
            TTFont(
                "DejaVu-Bold",
                str(bold_path),
            )
        )
        FONT_BOLD = "DejaVu-Bold"


def shorten(value, maximum=58):
    value = str(value or "").strip()

    if len(value) <= maximum:
        return value

    return f"{value[: maximum - 3]}..."


def build_qr_image(participation):
    payload = f"DS1:{participation.card_code}"

    qr = qrcode.QRCode(
        version=None,
        error_correction=(
            qrcode.constants.ERROR_CORRECT_H
        ),
        box_size=8,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)

    return ImageReader(output), payload


def draw_fiducials(pdf):
    page_width, page_height = A4

    size = 5 * mm
    margin = 7 * mm

    coordinates = (
        (margin, margin),
        (page_width - margin - size, margin),
        (margin, page_height - margin - size),
        (
            page_width - margin - size,
            page_height - margin - size,
        ),
    )

    pdf.setFillColor(black)
    pdf.setStrokeColor(black)

    for x, y in coordinates:
        pdf.rect(
            x,
            y,
            size,
            size,
            fill=1,
            stroke=0,
        )


def draw_header(pdf, participation):
    application = participation.application
    student = participation.student
    classroom = (
        participation.application_classroom.classroom
    )

    page_width, page_height = A4

    pdf.setFillColor(BLUE)
    pdf.roundRect(
        17 * mm,
        page_height - 43 * mm,
        176 * mm,
        27 * mm,
        4 * mm,
        fill=1,
        stroke=0,
    )

    pdf.setFillColor(GOLD)
    pdf.setFont(FONT_BOLD, 15)
    pdf.drawString(
        23 * mm,
        page_height - 26 * mm,
        "DINÂMICA SIMULADOS",
    )

    pdf.setFillColor(white)
    pdf.setFont(FONT_BOLD, 9)
    pdf.drawString(
        23 * mm,
        page_height - 33 * mm,
        "CARTÃO-RESPOSTA INDIVIDUAL",
    )

    pdf.setFont(FONT_REGULAR, 7)
    pdf.drawString(
        23 * mm,
        page_height - 38 * mm,
        shorten(application.title, 65),
    )

    qr_image, _ = build_qr_image(participation)

    pdf.setFillColor(white)
    pdf.roundRect(
        160 * mm,
        page_height - 41 * mm,
        29 * mm,
        29 * mm,
        2 * mm,
        fill=1,
        stroke=0,
    )

    pdf.drawImage(
        qr_image,
        162 * mm,
        page_height - 39 * mm,
        width=25 * mm,
        height=25 * mm,
        preserveAspectRatio=True,
        mask="auto",
    )

    pdf.setFillColor(black)
    pdf.setStrokeColor(LIGHT_GRAY)

    info_top = page_height - 49 * mm
    row_height = 7 * mm

    fields = (
        (
            "ALUNO",
            shorten(student.full_name, 48),
            "MATRÍCULA",
            student.registration_code,
        ),
        (
            "ESCOLA",
            shorten(classroom.school.name, 43),
            "TURMA",
            shorten(classroom, 22),
        ),
        (
            "MUNICÍPIO",
            shorten(application.municipality, 35),
            "TURNO",
            classroom.get_shift_display(),
        ),
        (
            "APLICAÇÃO",
            application.application_date.strftime(
                "%d/%m/%Y"
            ),
            "VERSÃO",
            participation.assessment_version.code,
        ),
    )

    for index, field in enumerate(fields):
        y = info_top - index * row_height

        pdf.setFillColor(LIGHT_BLUE)
        pdf.rect(
            17 * mm,
            y - 5.5 * mm,
            176 * mm,
            6.5 * mm,
            fill=1,
            stroke=0,
        )

        pdf.setFillColor(BLUE)
        pdf.setFont(FONT_BOLD, 6.5)
        pdf.drawString(
            20 * mm,
            y - 2.5 * mm,
            field[0],
        )

        pdf.setFillColor(black)
        pdf.setFont(FONT_REGULAR, 7.5)
        pdf.drawString(
            36 * mm,
            y - 2.5 * mm,
            str(field[1]),
        )

        pdf.setFillColor(BLUE)
        pdf.setFont(FONT_BOLD, 6.5)
        pdf.drawString(
            135 * mm,
            y - 2.5 * mm,
            field[2],
        )

        pdf.setFillColor(black)
        pdf.setFont(FONT_REGULAR, 7.5)
        pdf.drawString(
            153 * mm,
            y - 2.5 * mm,
            str(field[3]),
        )

    pdf.setFillColor(GRAY)
    pdf.setFont(FONT_REGULAR, 6.5)
    pdf.drawString(
        18 * mm,
        page_height - 80 * mm,
        (
            "Preencha completamente apenas uma alternativa "
            "por questão. Não dobre ou rasgue esta folha."
        ),
    )

    pdf.setFillColor(BLUE)
    pdf.setFont(FONT_BOLD, 7)
    pdf.drawRightString(
        192 * mm,
        page_height - 80 * mm,
        (
            f"CÓDIGO: {participation.short_card_code} "
            f"| Nº {participation.sequence_number}"
        ),
    )


def draw_answer_column(
    pdf,
    questions,
    x,
    top_y,
    width,
    option_count,
):
    if not questions:
        return

    component = questions[0].component

    if component:
        component_title = component.title.upper()
    else:
        component_title = "QUESTÕES"

    pdf.setFillColor(BLUE)
    pdf.roundRect(
        x,
        top_y,
        width,
        9 * mm,
        2 * mm,
        fill=1,
        stroke=0,
    )

    pdf.setFillColor(white)
    pdf.setFont(FONT_BOLD, 9)
    pdf.drawCentredString(
        x + width / 2,
        top_y + 3.2 * mm,
        shorten(component_title, 28),
    )

    number_x = x + 8 * mm
    first_option_x = x + 27 * mm
    option_spacing = 11 * mm
    row_height = 7.7 * mm

    header_y = top_y - 5.5 * mm

    pdf.setFillColor(GRAY)
    pdf.setFont(FONT_BOLD, 7)

    for option_index in range(option_count):
        option_letter = chr(
            ord("A") + option_index
        )

        option_x = (
            first_option_x
            + option_index * option_spacing
        )

        pdf.drawCentredString(
            option_x,
            header_y,
            option_letter,
        )

    for row_index, question in enumerate(questions):
        row_y = (
            top_y
            - 11 * mm
            - row_index * row_height
        )

        if row_index % 2 == 0:
            pdf.setFillColor(LIGHT_BLUE)
            pdf.rect(
                x,
                row_y - 2.2 * mm,
                width,
                6.5 * mm,
                fill=1,
                stroke=0,
            )

        pdf.setFillColor(black)
        pdf.setFont(FONT_BOLD, 7.5)
        pdf.drawRightString(
            number_x + 4 * mm,
            row_y,
            str(question.number),
        )

        for option_index in range(option_count):
            option_x = (
                first_option_x
                + option_index * option_spacing
            )

            pdf.setStrokeColor(black)
            pdf.setLineWidth(0.8)
            pdf.setFillColor(white)

            pdf.circle(
                option_x,
                row_y + 0.5 * mm,
                2.6 * mm,
                fill=0,
                stroke=1,
            )


def draw_answer_area(pdf, participation):
    questions = list(
        participation.assessment_version.questions
        .select_related(
            "component",
            "component__subject",
        )
        .filter(is_active=True)
        .order_by("number")
    )

    expected_count = (
        participation.assessment_version.question_count
    )

    if len(questions) != expected_count:
        raise ValidationError(
            (
                f"A versão {participation.assessment_version.code} "
                f"espera {expected_count} questões, mas possui "
                f"{len(questions)} questões ativas."
            )
        )

    if expected_count > 40:
        raise ValidationError(
            "A versão Light aceita no máximo 40 questões "
            "por cartão."
        )

    option_count = (
        participation.assessment_version.option_count
    )

    left_questions = questions[:20]
    right_questions = questions[20:40]

    top_y = 202 * mm
    column_width = 79 * mm

    draw_answer_column(
        pdf,
        left_questions,
        x=20 * mm,
        top_y=top_y,
        width=column_width,
        option_count=option_count,
    )

    if right_questions:
        draw_answer_column(
            pdf,
            right_questions,
            x=111 * mm,
            top_y=top_y,
            width=column_width,
            option_count=option_count,
        )


def draw_footer(pdf, participation, page_number):
    pdf.setStrokeColor(LIGHT_GRAY)
    pdf.line(
        18 * mm,
        19 * mm,
        192 * mm,
        19 * mm,
    )

    pdf.setFillColor(GRAY)
    pdf.setFont(FONT_REGULAR, 6.2)

    pdf.drawString(
        20 * mm,
        14 * mm,
        (
            "Uso institucional - Dinâmica Simulados. "
            "QR Code sem dados pessoais."
        ),
    )

    pdf.drawRightString(
        190 * mm,
        14 * mm,
        (
            f"{participation.application.code} "
            f"| página {page_number}"
        ),
    )


def draw_answer_sheet(
    pdf,
    participation,
    page_number,
):
    draw_fiducials(pdf)
    draw_header(pdf, participation)
    draw_answer_area(pdf, participation)
    draw_footer(
        pdf,
        participation,
        page_number,
    )
    pdf.showPage()


def generate_answer_sheets_pdf(participations):
    register_fonts()

    participations = list(participations)

    if not participations:
        raise ValidationError(
            "Nenhuma participação foi selecionada."
        )

    output = BytesIO()

    pdf = canvas.Canvas(
        output,
        pagesize=A4,
        pageCompression=1,
    )
    pdf.setTitle(
        "Cartões-resposta - Dinâmica Simulados"
    )
    pdf.setAuthor("Editora Dinâmica")

    for page_number, participation in enumerate(
        participations,
        start=1,
    ):
        draw_answer_sheet(
            pdf,
            participation,
            page_number,
        )

    pdf.save()
    output.seek(0)

    reader = PdfReader(output)

    if len(reader.pages) != len(participations):
        raise ValidationError(
            "A quantidade de páginas gerada não corresponde "
            "à quantidade de participantes."
        )

    output.seek(0)

    return output
