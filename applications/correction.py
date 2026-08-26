from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    AnswerEntry,
    AnswerSheet,
    AnswerSheetBreakdown,
    Participation,
)


ZERO = Decimal("0.00")
ONE_HUNDRED = Decimal("100.00")
MONEY_QUANTIZER = Decimal("0.01")


def quantize(value):
    return Decimal(value).quantize(
        MONEY_QUANTIZER,
        rounding=ROUND_HALF_UP,
    )


def get_actor(user):
    if user and getattr(user, "is_authenticated", False):
        return user

    return None


def validate_participation(participation):
    if participation.status == Participation.Status.ABSENT:
        raise ValidationError(
            "Não é possível lançar respostas para aluno ausente."
        )

    if participation.status == Participation.Status.CANCELLED:
        raise ValidationError(
            "Não é possível lançar respostas para participação "
            "cancelada."
        )


@transaction.atomic
def initialize_answer_sheet(
    participation,
    user=None,
):
    participation = (
        Participation.objects.select_for_update()
        .select_related(
            "application",
            "student",
            "assessment_version",
        )
        .get(pk=participation.pk)
    )

    validate_participation(participation)

    version = participation.assessment_version

    questions = list(
        version.questions.filter(
            is_active=True,
        )
        .select_related(
            "component",
        )
        .order_by("number")
    )

    if len(questions) != version.question_count:
        raise ValidationError(
            (
                f"A versão {version.code} espera "
                f"{version.question_count} questões, mas possui "
                f"{len(questions)} questões ativas."
            )
        )

    answer_sheet, created = (
        AnswerSheet.objects.select_for_update()
        .get_or_create(
            participation=participation,
            defaults={
                "status": AnswerSheet.Status.DRAFT,
                "input_method": (
                    AnswerSheet.InputMethod.MANUAL
                ),
                "question_count": len(questions),
                "entered_by": get_actor(user),
            },
        )
    )

    if answer_sheet.status == AnswerSheet.Status.PROCESSED:
        raise ValidationError(
            "Este cartão já foi processado. Use o fluxo de "
            "reabertura antes de alterar as respostas."
        )

    answer_sheet.question_count = len(questions)

    if not answer_sheet.entered_by_id:
        answer_sheet.entered_by = get_actor(user)

    answer_sheet.save(
        update_fields=[
            "question_count",
            "entered_by",
            "updated_at",
        ]
    )

    existing_question_ids = set(
        answer_sheet.answers.values_list(
            "question_id",
            flat=True,
        )
    )

    missing_answers = [
        AnswerEntry(
            answer_sheet=answer_sheet,
            question=question,
            marking_status=(
                AnswerEntry.MarkingStatus.BLANK
            ),
        )
        for question in questions
        if question.pk not in existing_question_ids
    ]

    if missing_answers:
        AnswerEntry.objects.bulk_create(
            missing_answers
        )

    invalid_answers = answer_sheet.answers.exclude(
        question__version=version,
    )

    if invalid_answers.exists():
        raise ValidationError(
            "O cartão possui respostas de outra versão da prova."
        )

    return answer_sheet, created


def component_identity(question):
    if question.component_id:
        return (
            question.component.code,
            question.component.title,
        )

    subject = question.version.assessment.subject

    if subject:
        return (
            f"SUBJECT-{subject.pk}",
            subject.name,
        )

    return (
        "SEM-COMPONENTE",
        "Sem componente informado",
    )


def descriptor_identity(question):
    code = (
        question.descriptor_code.strip().upper()
        if question.descriptor_code
        else "SEM-DESCRITOR"
    )

    label = (
        question.descriptor.strip()
        if question.descriptor
        else "Sem descritor informado"
    )

    return code, label


def build_group_data():
    return {
        "questions": 0,
        "answered": 0,
        "correct": 0,
        "incorrect": 0,
        "blank": 0,
        "multiple": 0,
        "score": ZERO,
        "maximum_score": ZERO,
        "label": "",
    }


def add_answer_to_group(
    group,
    answer,
    question_maximum_score,
):
    group["questions"] += 1
    group["maximum_score"] += question_maximum_score
    group["score"] += answer.awarded_score

    if (
        answer.marking_status
        == AnswerEntry.MarkingStatus.BLANK
    ):
        group["blank"] += 1
        return

    if (
        answer.marking_status
        == AnswerEntry.MarkingStatus.MULTIPLE
    ):
        group["multiple"] += 1
        return

    group["answered"] += 1

    if answer.is_correct:
        group["correct"] += 1
    else:
        group["incorrect"] += 1


def save_breakdowns(
    answer_sheet,
    answers,
    total_weight,
    total_score,
):
    groups = {
        AnswerSheetBreakdown.Dimension.COMPONENT: defaultdict(
            build_group_data
        ),
        AnswerSheetBreakdown.Dimension.DESCRIPTOR: defaultdict(
            build_group_data
        ),
    }

    for answer in answers:
        question = answer.question

        question_maximum_score = (
            question.weight
            / total_weight
            * total_score
        )

        component_key, component_label = (
            component_identity(question)
        )
        descriptor_key, descriptor_label = (
            descriptor_identity(question)
        )

        component_group = groups[
            AnswerSheetBreakdown.Dimension.COMPONENT
        ][component_key]
        component_group["label"] = component_label

        add_answer_to_group(
            component_group,
            answer,
            question_maximum_score,
        )

        descriptor_group = groups[
            AnswerSheetBreakdown.Dimension.DESCRIPTOR
        ][descriptor_key]
        descriptor_group["label"] = descriptor_label

        add_answer_to_group(
            descriptor_group,
            answer,
            question_maximum_score,
        )

    AnswerSheetBreakdown.objects.filter(
        answer_sheet=answer_sheet,
    ).delete()

    breakdowns = []

    for dimension, dimension_groups in groups.items():
        for key, group in dimension_groups.items():
            maximum_score = quantize(
                group["maximum_score"]
            )
            score = quantize(group["score"])

            if maximum_score:
                percentage = quantize(
                    score
                    / maximum_score
                    * ONE_HUNDRED
                )
            else:
                percentage = ZERO

            breakdowns.append(
                AnswerSheetBreakdown(
                    answer_sheet=answer_sheet,
                    dimension=dimension,
                    key=key,
                    label=group["label"],
                    question_count=group["questions"],
                    answered_count=group["answered"],
                    correct_count=group["correct"],
                    incorrect_count=group["incorrect"],
                    blank_count=group["blank"],
                    multiple_count=group["multiple"],
                    score=score,
                    maximum_score=maximum_score,
                    percentage=percentage,
                )
            )

    AnswerSheetBreakdown.objects.bulk_create(
        breakdowns
    )


@transaction.atomic
def process_answer_sheet(
    answer_sheet,
    user=None,
):
    answer_sheet = (
        AnswerSheet.objects.select_for_update()
        .select_related(
            "participation",
            "participation__application",
            "participation__assessment_version",
        )
        .get(pk=answer_sheet.pk)
    )

    participation = answer_sheet.participation
    validate_participation(participation)

    version = participation.assessment_version

    questions = list(
        version.questions.filter(
            is_active=True,
        )
        .select_related(
            "component",
            "version",
            "version__assessment",
            "version__assessment__subject",
        )
        .order_by("number")
    )

    if len(questions) != version.question_count:
        raise ValidationError(
            (
                f"A versão {version.code} espera "
                f"{version.question_count} questões, mas possui "
                f"{len(questions)} questões ativas."
            )
        )

    questions_without_key = [
        str(question.number)
        for question in questions
        if not question.correct_answer
    ]

    if questions_without_key:
        raise ValidationError(
            (
                "O gabarito está incompleto nas questões: "
                f"{', '.join(questions_without_key)}."
            )
        )

    answers = list(
        answer_sheet.answers.select_related(
            "question",
            "question__component",
            "question__version",
            "question__version__assessment",
            "question__version__assessment__subject",
        )
        .order_by("question__number")
    )

    if len(answers) != len(questions):
        raise ValidationError(
            (
                f"O cartão possui {len(answers)} respostas "
                f"registradas, mas deveria possuir "
                f"{len(questions)}."
            )
        )

    expected_question_ids = {
        question.pk
        for question in questions
    }
    answer_question_ids = {
        answer.question_id
        for answer in answers
    }

    if answer_question_ids != expected_question_ids:
        raise ValidationError(
            "As respostas não correspondem exatamente às "
            "questões da versão atribuída."
        )

    total_weight = sum(
        (
            question.weight
            for question in questions
        ),
        ZERO,
    )

    if total_weight <= ZERO:
        raise ValidationError(
            "A versão não possui peso total válido."
        )

    answered_count = 0
    blank_count = 0
    multiple_count = 0
    correct_count = 0
    incorrect_count = 0
    correct_weight = ZERO

    for answer in answers:
        answer.full_clean()

        question = answer.question

        if (
            answer.marking_status
            == AnswerEntry.MarkingStatus.BLANK
        ):
            blank_count += 1
            answer.is_correct = False
            answer.awarded_score = ZERO

        elif (
            answer.marking_status
            == AnswerEntry.MarkingStatus.MULTIPLE
        ):
            multiple_count += 1
            answer.is_correct = False
            answer.awarded_score = ZERO

        else:
            answered_count += 1

            answer.is_correct = (
                answer.selected_answer
                == question.correct_answer
            )

            if answer.is_correct:
                correct_count += 1
                correct_weight += question.weight
                answer.awarded_score = quantize(
                    question.weight
                    / total_weight
                    * version.total_score
                )
            else:
                incorrect_count += 1
                answer.awarded_score = ZERO

        answer.save(
            update_fields=[
                "is_correct",
                "awarded_score",
                "updated_at",
            ]
        )

    score = quantize(
        correct_weight
        / total_weight
        * version.total_score
    )

    if version.total_score:
        percentage = quantize(
            score
            / version.total_score
            * ONE_HUNDRED
        )
    else:
        percentage = ZERO

    answer_sheet.question_count = len(questions)
    answer_sheet.answered_count = answered_count
    answer_sheet.blank_count = blank_count
    answer_sheet.multiple_count = multiple_count
    answer_sheet.correct_count = correct_count
    answer_sheet.incorrect_count = incorrect_count
    answer_sheet.score = score
    answer_sheet.percentage = percentage
    answer_sheet.status = AnswerSheet.Status.PROCESSED
    answer_sheet.processed_by = get_actor(user)
    answer_sheet.processed_at = timezone.now()
    answer_sheet.processing_message = (
        "Correção concluída com sucesso."
    )

    if not answer_sheet.entered_at:
        answer_sheet.entered_at = timezone.now()

    if not answer_sheet.entered_by_id:
        answer_sheet.entered_by = get_actor(user)

    answer_sheet.save(
        update_fields=[
            "question_count",
            "answered_count",
            "blank_count",
            "multiple_count",
            "correct_count",
            "incorrect_count",
            "score",
            "percentage",
            "status",
            "processed_by",
            "processed_at",
            "processing_message",
            "entered_by",
            "entered_at",
            "updated_at",
        ]
    )

    save_breakdowns(
        answer_sheet=answer_sheet,
        answers=answers,
        total_weight=total_weight,
        total_score=version.total_score,
    )

    participation.status = Participation.Status.PROCESSED
    participation.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return answer_sheet