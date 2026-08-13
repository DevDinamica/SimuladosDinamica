from django.urls import path

from . import views


app_name = "requests_app"

urlpatterns = [
    path(
        "",
        views.simulation_request_create,
        name="create",
    ),
    path(
        "confirmacao/<str:protocol>/",
        views.simulation_request_success,
        name="success",
    ),
]