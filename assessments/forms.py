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
            versions = self.instance.versions.filter(
                is_active=True,
            )

            if not versions.exists():
                raise ValidationError(
                    "Cadastre pelo menos uma versão antes de publicar."
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

        return cleaned_data
