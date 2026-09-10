from django import forms

from institutions.models import School
from applications.models import (
    AnswerSheetImageSubmission,
    ApplicationClassroom,
    Participation,
)


class CardSubmissionForm(
    forms.ModelForm
):
    school = forms.ModelChoiceField(
        label="Escola",
        queryset=School.objects.none(),
        empty_label="Selecione a escola",
    )
    application_classroom = (
        forms.ModelChoiceField(
            label="Turma",
            queryset=(
                ApplicationClassroom
                .objects
                .none()
            ),
            empty_label=(
                "Selecione primeiro a escola"
            ),
        )
    )
    participation = (
        forms.ModelChoiceField(
            label="Aluno",
            queryset=(
                Participation
                .objects
                .none()
            ),
            empty_label=(
                "Selecione primeiro a turma"
            ),
        )
    )

    class Meta:
        model = AnswerSheetImageSubmission
        fields = (
            "school",
            "application_classroom",
            "participation",
            "sender_name",
            "image",
        )
        labels = {
            "sender_name": (
                "Nome de quem está enviando"
            ),
            "image": (
                "Foto do cartão-resposta"
            ),
        }
        widgets = {
            "sender_name": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Nome do encarregado"
                    ),
                    "autocomplete": "name",
                }
            ),
            "image": forms.ClearableFileInput(
                attrs={
                    "accept": (
                        "image/jpeg,"
                        "image/png,"
                        "image/webp"
                    ),
                    "capture": "environment",
                }
            ),
        }
        help_texts = {
            "image": (
                "Fotografe o cartão inteiro, "
                "sem cortar os marcadores."
            ),
        }

    def __init__(
        self,
        *args,
        portal,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.portal = portal
        application = portal.application

        self.fields[
            "school"
        ].queryset = (
            School.objects
            .filter(
                classrooms__simulation_applications__application=(
                    application
                ),
                classrooms__simulation_applications__is_active=True,
            )
            .distinct()
            .order_by("name")
        )

        school_id = self.data.get(
            "school"
        )

        if school_id:
            self.fields[
                "application_classroom"
            ].queryset = (
                ApplicationClassroom
                .objects
                .filter(
                    application=application,
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

        application_classroom_id = (
            self.data.get(
                "application_classroom"
            )
        )

        if application_classroom_id:
            self.fields[
                "participation"
            ].queryset = (
                Participation.objects
                .filter(
                    application=application,
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

    def clean(self):
        cleaned_data = super().clean()

        school = cleaned_data.get(
            "school"
        )
        application_classroom = (
            cleaned_data.get(
                "application_classroom"
            )
        )
        participation = cleaned_data.get(
            "participation"
        )

        if (
            school
            and application_classroom
            and application_classroom
            .classroom
            .school_id
            != school.pk
        ):
            self.add_error(
                "application_classroom",
                (
                    "A turma selecionada não "
                    "pertence à escola."
                ),
            )

        if (
            application_classroom
            and participation
            and participation
            .application_classroom_id
            != application_classroom.pk
        ):
            self.add_error(
                "participation",
                (
                    "O aluno selecionado não "
                    "pertence à turma."
                ),
            )

        if (
            participation
            and participation.application_id
            != self.portal.application_id
        ):
            self.add_error(
                "participation",
                (
                    "O aluno não pertence a "
                    "esta aplicação."
                ),
            )

        return cleaned_data

    def save(self, commit=True):
        submission = super().save(
            commit=False
        )
        submission.portal = self.portal

        if commit:
            submission.save()

        return submission