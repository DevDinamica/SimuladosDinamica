from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import SimulationRequest


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
            "estimated_question_count",
            "objective",
            "objective_details",
            "assessment_source",
            "print_responsibility",
            "applicator_responsibility",
            "has_scanning_devices",
            "internet_quality",
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