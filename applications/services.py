from itertools import cycle

from django.core.exceptions import ValidationError
from django.db import transaction

from academics.models import Enrollment

from .models import (
    ApplicationAssessment,
    Participation,
    ParticipationCard,
)


def participation_card_status(
    participation,
):
    status_mapping = {
        Participation.Status.EXPECTED: (
            ParticipationCard.Status.EXPECTED
        ),
        Participation.Status.PRESENT: (
            ParticipationCard.Status.EXPECTED
        ),
        Participation.Status.ABSENT: (
            ParticipationCard.Status.CANCELLED
        ),
        Participation.Status.ANSWER_SHEET_RECEIVED: (
            ParticipationCard.Status.RECEIVED
        ),
        Participation.Status.PROCESSED: (
            ParticipationCard.Status.PROCESSED
        ),
        Participation.Status.CANCELLED: (
            ParticipationCard.Status.CANCELLED
        ),
    }

    return status_mapping.get(
        participation.status,
        ParticipationCard.Status.EXPECTED,
    )


def ensure_primary_application_assessment(
    application,
):
    link, _ = (
        ApplicationAssessment.objects.get_or_create(
            application=application,
            assessment=application.assessment,
            defaults={
                "order": 1,
                "is_active": True,
            },
        )
    )

    return link


@transaction.atomic
def sync_participation_cards(
    participation,
):
    ensure_primary_application_assessment(
        participation.application
    )

    application_assessments = (
        participation.application
        .application_assessments
        .filter(
            is_active=True,
        )
        .select_related(
            "assessment",
        )
        .order_by(
            "order",
            "pk",
        )
    )

    created_count = 0
    existing_count = 0

    for application_assessment in (
        application_assessments
    ):
        versions = list(
            application_assessment
            .assessment
            .versions
            .filter(
                is_active=True,
            )
            .order_by("code")
        )

        if not versions:
            raise ValidationError(
                (
                    "A prova "
                    f"{application_assessment.assessment} "
                    "não possui versões ativas."
                )
            )

        if (
            participation.assessment_version.assessment_id
            == application_assessment.assessment_id
        ):
            version = (
                participation.assessment_version
            )
        else:
            sequence = (
                participation.sequence_number
                or participation.pk
                or 1
            )

            version_index = (
                sequence - 1
            ) % len(versions)

            version = versions[
                version_index
            ]

        _, created = (
            ParticipationCard.objects.get_or_create(
                participation=participation,
                application_assessment=(
                    application_assessment
                ),
                defaults={
                    "assessment_version": version,
                    "status": (
                        participation_card_status(
                            participation
                        )
                    ),
                },
            )
        )

        if created:
            created_count += 1
        else:
            existing_count += 1

    return created_count, existing_count


@transaction.atomic
def generate_application_participations(
    application,
):
    ensure_primary_application_assessment(
        application
    )

    versions = list(
        application.assessment.versions.filter(
            is_active=True,
        ).order_by("code")
    )

    if not versions:
        raise ValidationError(
            "A prova principal não possui versões ativas."
        )

    application_assessments = (
        application.application_assessments
        .filter(
            is_active=True,
        )
        .select_related(
            "assessment",
        )
    )

    for application_assessment in (
        application_assessments
    ):
        if not (
            application_assessment
            .assessment
            .versions
            .filter(
                is_active=True,
            )
            .exists()
        ):
            raise ValidationError(
                (
                    "A prova "
                    f"{application_assessment.assessment} "
                    "não possui versões ativas."
                )
            )

    application_classrooms = (
        application.application_classrooms.filter(
            is_active=True,
        )
        .select_related("classroom")
        .order_by(
            "classroom__school__name",
            "classroom__grade__order",
            "classroom__name",
        )
    )

    if not application_classrooms.exists():
        raise ValidationError(
            "Adicione pelo menos uma turma à aplicação."
        )

    created_count = 0
    existing_count = 0

    for application_classroom in (
        application_classrooms
    ):
        enrollments = (
            Enrollment.objects.filter(
                classroom=(
                    application_classroom.classroom
                ),
                status=Enrollment.Status.ACTIVE,
                student__is_active=True,
            )
            .select_related("student")
            .order_by("student__full_name")
        )

        version_rotation = cycle(
            versions
        )

        for enrollment in enrollments:
            version = next(
                version_rotation
            )

            participation, created = (
                Participation.objects.get_or_create(
                    application=application,
                    student=enrollment.student,
                    defaults={
                        "application_classroom": (
                            application_classroom
                        ),
                        "enrollment": enrollment,
                        "assessment_version": version,
                    },
                )
            )

            sync_participation_cards(
                participation
            )

            if created:
                created_count += 1
            else:
                existing_count += 1

    return created_count, existing_count