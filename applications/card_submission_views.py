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
from django.urls import reverse

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

def request_expects_json(request):
    return (
        request.headers.get(
            "X-Requested-With"
        )
        == "XMLHttpRequest"
    )


def form_errors_as_json(form):
    errors = {}

    for field_name, field_errors in (
        form.errors.get_json_data()
        .items()
    ):
        errors[field_name] = [
            item["message"]
            for item in field_errors
        ]

    return errors


def participation_has_all_cards(
    participation,
):
    pending_cards_exist = (
        ParticipationCard.objects
        .filter(
            participation=participation,
            application_assessment__is_active=True,
        )
        .exclude(
            status__in=[
                ParticipationCard.Status.RECEIVED,
                ParticipationCard.Status.PROCESSED,
                ParticipationCard.Status.CANCELLED,
            ],
        )
        .exists()
    )

    return not pending_cards_exist


def update_participation_receipt_status(
    participation,
):
    if participation.status not in {
        Participation.Status.EXPECTED,
        Participation.Status.PRESENT,
        Participation.Status.ANSWER_SHEET_RECEIVED,
    }:
        return

    if participation_has_all_cards(
        participation
    ):
        new_status = (
            Participation.Status
            .ANSWER_SHEET_RECEIVED
        )
    else:
        new_status = (
            Participation.Status.PRESENT
        )

    if participation.status != new_status:
        Participation.objects.filter(
            pk=participation.pk,
        ).update(
            status=new_status,
        )

        participation.status = new_status

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

    if request.method == "POST":
        if not form.is_valid():
            if request_expects_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "errors": (
                            form_errors_as_json(
                                form
                            )
                        ),
                    },
                    status=422,
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

        with transaction.atomic():
            selected_card = (
                form.cleaned_data[
                    "participation_card"
                ]
            )

            locked_card = (
                ParticipationCard.objects
                .select_for_update()
                .get(
                    pk=selected_card.pk,
                )
            )

            active_submission_exists = (
                AnswerSheetImageSubmission
                .objects
                .filter(
                    portal=portal,
                    participation_card=(
                        locked_card
                    ),
                    status__in=[
                        (
                            AnswerSheetImageSubmission
                            .Status
                            .RECEIVED
                        ),
                        (
                            AnswerSheetImageSubmission
                            .Status
                            .UNDER_REVIEW
                        ),
                        (
                            AnswerSheetImageSubmission
                            .Status
                            .ACCEPTED
                        ),
                    ],
                )
                .exists()
            )

            if active_submission_exists:
                message = (
                    "Este cartão já foi enviado. "
                    "Guarde o protocolo anterior "
                    "ou procure a Editora para "
                    "solicitar a substituição."
                )

                if request_expects_json(request):
                    return JsonResponse(
                        {
                            "success": False,
                            "duplicate": True,
                            "errors": {
                                "participation_card": [
                                    message
                                ],
                            },
                        },
                        status=409,
                    )

                form.add_error(
                    "participation_card",
                    message,
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

            submission = form.save(
                commit=False
            )
            submission.participation_card = (
                locked_card
            )
            submission.participation = (
                locked_card.participation
            )
            submission.save()

            if locked_card.status != (
                ParticipationCard.Status.RECEIVED
            ):
                locked_card.status = (
                    ParticipationCard
                    .Status
                    .RECEIVED
                )
                locked_card.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

            update_participation_receipt_status(
                locked_card.participation
            )

        if request_expects_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "submission_code": str(
                        submission.submission_code
                    ),
                    "protocol": (
                        submission.protocol
                    ),
                    "card": {
                        "id": (
                            locked_card.pk
                        ),
                        "subject": (
                            locked_card
                            .subject_name
                        ),
                        "version": (
                            locked_card
                            .assessment_version
                            .code
                        ),
                        "code": (
                            locked_card
                            .short_card_code
                        ),
                    },
                    "participation_complete": (
                        locked_card
                        .participation
                        .status
                        == (
                            Participation
                            .Status
                            .ANSWER_SHEET_RECEIVED
                        )
                    ),
                    "success_url": reverse(
                        (
                            "card_submission:"
                            "success"
                        ),
                        kwargs={
                            "token": (
                                portal.token
                            ),
                            "submission_code": (
                                submission
                                .submission_code
                            ),
                        },
                    ),
                },
                status=201,
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
            participation_id=(
                participation_id
            ),
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
            (
                "application_assessment__"
                "assessment"
            ),
            (
                "application_assessment__"
                "assessment__subject"
            ),
        )
        .prefetch_related(
            "image_submissions"
        )
        .order_by(
            "application_assessment__order",
        )
    )

    results = []

    for card in cards:
        active_submission = next(
            (
                submission
                for submission
                in card.image_submissions.all()
                if submission.status
                in {
                    (
                        AnswerSheetImageSubmission
                        .Status
                        .RECEIVED
                    ),
                    (
                        AnswerSheetImageSubmission
                        .Status
                        .UNDER_REVIEW
                    ),
                    (
                        AnswerSheetImageSubmission
                        .Status
                        .ACCEPTED
                    ),
                }
            ),
            None,
        )

        results.append(
            {
                "id": card.pk,
                "label": card.subject_name,
                "version": (
                    card.assessment_version.code
                ),
                "code": card.short_card_code,
                "status": card.status,
                "status_label": (
                    card.get_status_display()
                ),
                "already_received": (
                    active_submission
                    is not None
                ),
                "protocol": (
                    active_submission.protocol
                    if active_submission
                    else ""
                ),
            }
        )

    return JsonResponse(
        {
            "results": results,
        }
    )

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