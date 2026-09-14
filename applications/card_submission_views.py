from django.db import transaction
from django.http import (
    Http404,
    JsonResponse,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_GET,
)

from applications.card_submission_forms import (
    CardSubmissionForm,
)
from applications.models import (
    AnswerSheetImageSubmission,
    ApplicationClassroom,
    CardSubmissionPortal,
    Participation,
    ParticipationCard,
)

import mimetypes

from django.contrib.admin.views.decorators import (
    staff_member_required,
)
from django.http import FileResponse


def get_accessible_card_portal(token):
    portal = get_object_or_404(
        CardSubmissionPortal.objects
        .select_related(
            "application",
            "application__assessment",
            "application__municipality",
        ),
        token=token,
    )

    if not portal.can_be_accessed:
        raise Http404(
            "Este portal está encerrado "
            "ou expirado."
        )

    return portal


def card_submission_detail(
    request,
    token,
):
    portal = get_accessible_card_portal(
        token
    )

    form = CardSubmissionForm(
        request.POST or None,
        request.FILES or None,
        portal=portal,
    )

    if (
        request.method == "POST"
        and form.is_valid()
    ):
        with transaction.atomic():
            submission = form.save()
            
            ParticipationCard.objects.filter(
                pk=submission.participation_card_id,
                status=(
                    ParticipationCard.Status.EXPECTED
                ),
            ).update(
                status=(
                    ParticipationCard.Status.RECEIVED
                ),
            )

            Participation.objects.filter(
                pk=submission.participation_id,
                status__in=[
                    Participation.Status.EXPECTED,
                    Participation.Status.PRESENT,
                ],
            ).update(
                status=(
                    Participation.Status
                    .ANSWER_SHEET_RECEIVED
                )
            )

        return redirect(
            "card_submission:success",
            token=portal.token,
            submission_code=(
                submission.submission_code
            ),
        )

    return render(
        request,
        (
            "applications/"
            "card_submission_form.html"
        ),
        {
            "portal": portal,
            "form": form,
        },
    )


@require_GET
def classroom_options(
    request,
    token,
):
    portal = get_accessible_card_portal(
        token
    )
    school_id = request.GET.get(
        "school"
    )

    classrooms = (
        ApplicationClassroom.objects
        .filter(
            application=portal.application,
            classroom__school_id=school_id,
            is_active=True,
        )
        .select_related(
            "classroom",
            "classroom__grade",
        )
        .order_by(
            "classroom__grade__order",
            "classroom__name",
        )
    )

    results = []

    for item in classrooms:
        classroom = item.classroom

        results.append({
            "id": item.pk,
            "label": (
                f"{classroom.grade.name} "
                f"{classroom.name} — "
                f"{classroom.get_shift_display()}"
            ),
        })

    return JsonResponse({
        "results": results,
    })


@require_GET
def student_options(
    request,
    token,
):
    portal = get_accessible_card_portal(
        token
    )

    application_classroom_id = (
        request.GET.get(
            "application_classroom"
        )
    )

    participations = (
        Participation.objects
        .filter(
            application=portal.application,
            application_classroom_id=(
                application_classroom_id
            ),
        )
        .exclude(
            status__in=[
                Participation.Status.ABSENT,
                Participation.Status.CANCELLED,
            ]
        )
        .select_related(
            "student",
        )
        .order_by(
            "student__full_name",
        )
    )

    results = [
        {
            "id": participation.pk,
            "label": (
                participation
                .student
                .full_name
            ),
            "registration": (
                participation
                .student
                .registration_code
            ),
        }
        for participation in participations
    ]

    return JsonResponse({
        "results": results,
    })

@require_GET
def card_options(
    request,
    token,
):
    portal = get_accessible_card_portal(
        token
    )

    participation_id = request.GET.get(
        "participation"
    )

    cards = (
        ParticipationCard.objects
        .filter(
            participation_id=participation_id,
            participation__application=(
                portal.application
            ),
            application_assessment__is_active=True,
        )
        .exclude(
            status=(
                ParticipationCard.Status.CANCELLED
            ),
        )
        .select_related(
            "assessment_version",
            "application_assessment",
            "application_assessment__assessment",
            (
                "application_assessment__"
                "assessment__subject"
            ),
        )
        .order_by(
            "application_assessment__order",
        )
    )

    results = [
        {
            "id": card.pk,
            "label": card.subject_name,
            "version": (
                card.assessment_version.code
            ),
            "code": card.short_card_code,
        }
        for card in cards
    ]

    return JsonResponse({
        "results": results,
    })

def card_submission_success(
    request,
    token,
    submission_code,
):
    portal = get_accessible_card_portal(
        token
    )

    submission = get_object_or_404(
        AnswerSheetImageSubmission
        .objects
        .select_related(
            "participation",
            "participation__student",
            (
                "participation__"
                "application_classroom__"
                "classroom"
            ),
            (
                "participation__"
                "application_classroom__"
                "classroom__school"
            ),
            "participation_card",
            (
                "participation_card__"
                "assessment_version"
            ),
            (
                "participation_card__"
                "application_assessment__"
                "assessment"
            ),
            (
                "participation_card__"
                "application_assessment__"
                "assessment__subject"
            ),
        ),
        portal=portal,
        submission_code=submission_code,
    )

    return render(
        request,
        (
            "applications/"
            "card_submission_success.html"
        ),
        {
            "portal": portal,
            "submission": submission,
        },
    )
    
@staff_member_required
def secure_submission_image(
    request,
    submission_code,
):
    submission = get_object_or_404(
        AnswerSheetImageSubmission,
        submission_code=submission_code,
    )

    content_type, _ = (
        mimetypes.guess_type(
            submission.original_name
        )
    )

    response = FileResponse(
        submission.image.open("rb"),
        content_type=(
            content_type
            or "application/octet-stream"
        ),
    )
    response[
        "Content-Disposition"
    ] = (
        "inline; "
        f'filename="{submission.original_name}"'
    )
    response[
        "X-Content-Type-Options"
    ] = "nosniff"
    response[
        "Cache-Control"
    ] = "private, no-store"

    return response