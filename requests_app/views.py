from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import SimulationRequestForm
from .models import SimulationRequest


@require_http_methods(["GET", "POST"])
def simulation_request_create(request):
    if request.method == "POST":
        form = SimulationRequestForm(request.POST)

        if form.is_valid():
            simulation_request = form.save()

            request.session[
                "simulation_request_protocol"
            ] = simulation_request.protocol

            return redirect(
                "requests_app:success",
                protocol=simulation_request.protocol,
            )
    else:
        form = SimulationRequestForm()

    return render(
        request,
        "requests_app/request_form.html",
        {
            "form": form,
        },
    )


def simulation_request_success(request, protocol):
    session_protocol = request.session.get(
        "simulation_request_protocol"
    )

    if session_protocol != protocol:
        return redirect("requests_app:create")

    simulation_request = get_object_or_404(
        SimulationRequest,
        protocol=protocol,
    )

    return render(
        request,
        "requests_app/request_success.html",
        {
            "simulation_request": simulation_request,
        },
    )