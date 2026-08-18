from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import SpreadsheetUploadForm
from .models import DataPreparationPortal
from .services import validate_upload
from .workbook import build_student_import_workbook


def get_accessible_portal(token):
    portal = get_object_or_404(
        DataPreparationPortal.objects.select_related(
            "application",
            "application__assessment",
            "application__municipality",
        ),
        token=token,
    )

    if not portal.can_be_accessed:
        raise Http404(
            "Este portal está encerrado ou expirado."
        )

    return portal


def portal_detail(request, token):
    portal = get_accessible_portal(token)
    upload = portal.latest_upload

    return render(
        request,
        "data_portal/portal_detail.html",
        {
            "portal": portal,
            "upload": upload,
            "form": SpreadsheetUploadForm(),
        },
    )


def download_template(request, token):
    portal = get_accessible_portal(token)

    workbook = build_student_import_workbook(
        portal
    )

    filename = (
        f"modelo_alunos_{portal.application.code}.xlsx"
    )

    response = HttpResponse(
        workbook.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    return response


@require_POST
def upload_spreadsheet(request, token):
    portal = get_accessible_portal(token)
    form = SpreadsheetUploadForm(
        request.POST,
        request.FILES,
    )

    if not form.is_valid():
        return render(
            request,
            "data_portal/portal_detail.html",
            {
                "portal": portal,
                "upload": portal.latest_upload,
                "form": form,
            },
        )

    upload = form.save(commit=False)
    upload.portal = portal
    upload.original_name = request.FILES[
        "file"
    ].name
    upload.save()

    portal.status = (
        DataPreparationPortal.Status.FILE_RECEIVED
    )
    portal.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    validate_upload(upload)

    return redirect(
        "data_portal:detail",
        token=portal.token,
    )


@require_POST
def submit_for_review(request, token):
    portal = get_accessible_portal(token)
    upload = portal.latest_upload

    if not upload or upload.error_count:
        messages.error(
            request,
            "Corrija as pendências antes de confirmar o envio.",
        )

        return redirect(
            "data_portal:detail",
            token=portal.token,
        )

    portal.status = (
        DataPreparationPortal.Status.SUBMITTED
    )
    portal.submitted_at = timezone.now()
    portal.save()

    messages.success(
        request,
        "Dados enviados para revisão da Editora Dinâmica.",
    )

    return redirect(
        "data_portal:detail",
        token=portal.token,
    )