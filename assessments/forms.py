from django import forms
from django.core.exceptions import ValidationError

from .models import Assessment


class AssessmentAdminForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = "__all__"

def clean(self):
    cleaned_data = super().clean()
    status = cleaned_data.get("status")

    if (
        self.instance.pk
        and status == Assessment.Status.PUBLISHED
    ):
        assessment = self.instance

        versions = assessment.versions.filter(
            is_active=True,
        )

        if not versions.exists():
            raise ValidationError(
                "Cadastre pelo menos uma versão antes de publicar."
            )

        if not assessment.subject_id:
            if not assessment.components.filter(
                is_active=True,
            ).exists():
                raise ValidationError(
                    "Informe uma disciplina principal ou cadastre "
                    "os componentes curriculares da prova."
                )

        incomplete_versions = [
            version.code
            for version in versions
            if not version.is_answer_key_complete
        ]

        if incomplete_versions:
            codes = ", ".join(incomplete_versions)

            raise ValidationError(
                "Os gabaritos das seguintes versões estão "
                f"incompletos: {codes}."
            )

        if assessment.components.filter(
            is_active=True,
        ).exists():
            questions_without_component = (
                assessment.versions.filter(
                    is_active=True,
                    questions__component__isnull=True,
                )
                .values_list(
                    "questions__number",
                    flat=True,
                )
                .distinct()
                .order_by("questions__number")
            )

            missing_numbers = list(
                questions_without_component
            )

            if missing_numbers:
                numbers = ", ".join(
                    str(number)
                    for number in missing_numbers
                )

                raise ValidationError(
                    "As seguintes questões não possuem componente "
                    f"curricular: {numbers}."
                )

    return cleaned_data
