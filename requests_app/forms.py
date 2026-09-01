from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import SimulationRequest
from academics.models import Grade, Subject


class SimulationRequestForm(forms.ModelForm):
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta:
        model = SimulationRequest
        fields = (
            "requester_name",
            "requester_role",
            "requester_email",
            "requester_phone",
            "requester_institution",
            "state",
            "municipality_name",
            "request_scope",
            "education_department_name",
            "school_name",
            "school_inep_code",
            "preferred_date",
            "alternative_date",
            "academic_year",
            "grades",
            "subjects",
            "estimated_school_count",
            "estimated_classroom_count",
            "estimated_student_count",
            "objective",
            "objective_details",
            "notes",
            "privacy_accepted",
        )
        widgets = {
            "preferred_date": forms.DateInput(
                attrs={"type": "date"},
            ),
            "alternative_date": forms.DateInput(
                attrs={"type": "date"},
            ),
            "grades": forms.CheckboxSelectMultiple(),
            "subjects": forms.CheckboxSelectMultiple(),
            "notes": forms.Textarea(
                attrs={"rows": 5},
            ),
            "privacy_accepted": forms.CheckboxInput(),
        }
        help_texts = {
            "school_name": (
                "Preencha quando a solicitação envolver uma escola "
                "específica ou uma escola de referência."
            ),
            "estimated_student_count": (
                "Informe uma estimativa. A lista nominal será enviada "
                "posteriormente por um canal seguro."
            ),
            "privacy_accepted": (
                "Declaro possuir autorização institucional para realizar "
                "a solicitação e encaminhar posteriormente somente os "
                "dados necessários à aplicação."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["grades"].queryset = (
            Grade.objects.filter(
                name__in=[
                    "2º ano",
                    "5º ano",
                    "9º ano",
                ],
                is_active=True,
            )
            .select_related("stage")
            .order_by(
                "stage__order",
                "order",
            )
        )

        self.fields["subjects"].queryset = (
            Subject.objects.filter(
                name__in=[
                    "Língua Portuguesa",
                    "Matemática",
                ],
                is_active=True,
            ).order_by("name")
        )

    def clean_website(self):
        value = self.cleaned_data.get("website")

        if value:
            raise ValidationError("Envio inválido.")

        return value

    def clean_state(self):
        return self.cleaned_data["state"].strip().upper()

    def clean_requester_email(self):
        return self.cleaned_data[
            "requester_email"
        ].strip().lower()

    def clean(self):
        cleaned_data = super().clean()

        preferred_date = cleaned_data.get("preferred_date")
        alternative_date = cleaned_data.get("alternative_date")
        objective = cleaned_data.get("objective")
        objective_details = cleaned_data.get(
            "objective_details",
        )
        privacy_accepted = cleaned_data.get(
            "privacy_accepted",
        )

        if (
            preferred_date
            and preferred_date < timezone.localdate()
        ):
            self.add_error(
                "preferred_date",
                "A data desejada não pode estar no passado.",
            )

        if (
            alternative_date
            and preferred_date
            and alternative_date == preferred_date
        ):
            self.add_error(
                "alternative_date",
                "A data alternativa deve ser diferente da principal.",
            )

        if (
            objective
            == SimulationRequest.AssessmentObjective.OTHER
            and not objective_details
        ):
            self.add_error(
                "objective_details",
                "Descreva o objetivo da avaliação.",
            )

        if not privacy_accepted:
            self.add_error(
                "privacy_accepted",
                "É necessário confirmar a autorização institucional.",
            )

        return cleaned_data

    def save(self, commit=True):
        simulation_request = super().save(
            commit=False
        )

        selected_subjects = self.cleaned_data.get(
            "subjects"
        )

        if selected_subjects is not None:
            simulation_request.estimated_question_count = (
                selected_subjects.count() * 20
            )

        simulation_request.assessment_source = (
            SimulationRequest.AssessmentSource.PUBLISHER
        )
        simulation_request.print_responsibility = (
            SimulationRequest.PrintResponsibility.PUBLISHER
        )
        simulation_request.applicator_responsibility = (
            SimulationRequest.ApplicatorResponsibility.PUBLISHER
        )
        simulation_request.has_scanning_devices = False
        simulation_request.internet_quality = (
            SimulationRequest.InternetQuality.UNKNOWN
        )

        if commit:
            simulation_request.save()
            self.save_m2m()

        return simulation_request