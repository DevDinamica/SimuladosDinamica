from django.urls import path

from applications import (
    card_submission_views as views,
)


app_name = "card_submission"

urlpatterns = [
    path(
        (
            "arquivo/"
            "<uuid:submission_code>/"
        ),
        views.secure_submission_image,
        name="secure_image",
    ),
    path(
        "<uuid:token>/",
        views.card_submission_detail,
        name="detail",
    ),
    path(
        "<uuid:token>/turmas/",
        views.classroom_options,
        name="classrooms",
    ),
    path(
        "<uuid:token>/alunos/",
        views.student_options,
        name="students",
    ),
    path(
        "<uuid:token>/cartoes/",
        views.card_options,
        name="cards",
    ),
    path(
        (
            "<uuid:token>/sucesso/"
            "<uuid:submission_code>/"
        ),
        views.card_submission_success,
        name="success",
    ),
]