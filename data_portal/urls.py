from django.urls import path

from . import views


app_name = "data_portal"

urlpatterns = [
    path(
        "<uuid:token>/",
        views.portal_detail,
        name="detail",
    ),
    path(
        "<uuid:token>/modelo/",
        views.download_template,
        name="download_template",
    ),
    path(
        "<uuid:token>/enviar/",
        views.upload_spreadsheet,
        name="upload",
    ),
    path(
        "<uuid:token>/confirmar/",
        views.submit_for_review,
        name="submit",
    ),
]