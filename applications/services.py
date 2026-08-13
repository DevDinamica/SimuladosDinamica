from itertools import cycle

from django.core.exceptions import ValidationError
from django.db import transaction

from academics.models import Enrollment

from .models import Participation


@transaction.atomic
def generate_application_participations(application):
    versions = list(
        application.assessment.versions.filter(
            is_active=True,
        ).order_by("code")
    )

    if not versions:
        raise ValidationError(
            "A prova não possui versões ativas."
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

    for application_classroom in application_classrooms:
        enrollments = (
            Enrollment.objects.filter(
                classroom=application_classroom.classroom,
                status=Enrollment.Status.ACTIVE,
                student__is_active=True,
            )
            .select_related("student")
            .order_by("student__full_name")
        )

        version_rotation = cycle(versions)

        for enrollment in enrollments:
            version = next(version_rotation)

            _, created = Participation.objects.get_or_create(
                application=application,
                student=enrollment.student,
                defaults={
                    "application_classroom": application_classroom,
                    "enrollment": enrollment,
                    "assessment_version": version,
                },
            )

            if created:
                created_count += 1
            else:
                existing_count += 1

    return created_count, existing_count