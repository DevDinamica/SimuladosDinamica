import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from academics.models import Classroom, Enrollment, Student
from assessments.models import Assessment, AssessmentVersion
from institutions.models import Municipality
from requests_app.models import SimulationRequest


class SimulationApplication(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        PREPARING = "PREPARING", "Em preparação"
        READY = "READY", "Pronta para aplicação"
        IN_PROGRESS = "IN_PROGRESS", "Em aplicação"
        PROCESSING = "PROCESSING", "Processando gabaritos"
        COMPLETED = "COMPLETED", "Concluída"
        CANCELLED = "CANCELLED", "Cancelada"

    code = models.CharField(
        "código",
        max_length=40,
        unique=True,
        blank=True,
        editable=False,
    )
    title = models.CharField(
        "título da aplicação",
        max_length=200,
    )
    simulation_request = models.OneToOneField(
        SimulationRequest,
        verbose_name="solicitação de origem",
        on_delete=models.PROTECT,
        related_name="application",
        null=True,
        blank=True,
    )
    assessment = models.ForeignKey(
        Assessment,
        verbose_name="prova",
        on_delete=models.PROTECT,
        related_name="applications",
    )
    municipality = models.ForeignKey(
        Municipality,
        verbose_name="município",
        on_delete=models.PROTECT,
        related_name="simulation_applications",
    )
    application_date = models.DateField(
        "data da aplicação",
    )
    alternative_date = models.DateField(
        "data alternativa",
        null=True,
        blank=True,
    )
    start_time = models.TimeField(
        "horário inicial",
        null=True,
        blank=True,
    )
    end_time = models.TimeField(
        "horário final",
        null=True,
        blank=True,
    )
    status = models.CharField(
        "situação",
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    general_instructions = models.TextField(
        "instruções gerais",
        blank=True,
    )
    internal_notes = models.TextField(
        "observações internas",
        blank=True,
    )
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="coordenador interno",
        on_delete=models.SET_NULL,
        related_name="coordinated_applications",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        "criada em",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "atualizada em",
        auto_now=True,
    )

    class Meta:
        verbose_name = "aplicação de simulado"
        verbose_name_plural = "aplicações de simulados"
        ordering = ["-application_date", "title"]
        indexes = [
            models.Index(
                fields=["code"],
                name="application_code_idx",
            ),
            models.Index(
                fields=["status", "application_date"],
                name="application_status_date_idx",
            ),
        ]

    def clean(self):
        errors = {}

        if (
            self.assessment_id
            and self.assessment.status
            != Assessment.Status.PUBLISHED
        ):
            errors["assessment"] = (
                "A prova precisa estar publicada para ser aplicada."
            )

        if (
            self.assessment_id
            and not self.assessment.versions.filter(
                is_active=True,
            ).exists()
        ):
            errors["assessment"] = (
                "A prova precisa possuir ao menos uma versão ativa."
            )

        if (
            self.alternative_date
            and self.alternative_date == self.application_date
        ):
            errors["alternative_date"] = (
                "A data alternativa deve ser diferente da principal."
            )

        if (
            self.start_time
            and self.end_time
            and self.end_time <= self.start_time
        ):
            errors["end_time"] = (
                "O horário final deve ser posterior ao inicial."
            )

        if (
            self.simulation_request_id
            and self.simulation_request.status
            not in {
                SimulationRequest.Status.APPROVED,
                SimulationRequest.Status.PREPARING_DATA,
                SimulationRequest.Status.APPLICATION_CREATED,
            }
        ):
            errors["simulation_request"] = (
                "A solicitação precisa estar aprovada antes de ser "
                "convertida em aplicação."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        creating = self.pk is None

        self.full_clean()
        super().save(*args, **kwargs)

        if creating and not self.code:
            self.code = (
                f"APL-{self.application_date.year}-{self.pk:06d}"
            )

            type(self).objects.filter(pk=self.pk).update(
                code=self.code
            )

        if (
            self.simulation_request_id
            and self.simulation_request.status
            != SimulationRequest.Status.APPLICATION_CREATED
        ):
            SimulationRequest.objects.filter(
                pk=self.simulation_request_id,
            ).update(
                status=SimulationRequest.Status.APPLICATION_CREATED,
            )

    @property
    def classroom_count(self):
        return self.application_classrooms.count()

    @property
    def participant_count(self):
        return self.participations.count()

    @property
    def confirmed_participant_count(self):
        return self.participations.exclude(
            status=Participation.Status.CANCELLED,
        ).count()

    def __str__(self):
        return f"{self.code or 'Nova aplicação'} — {self.title}"


class ApplicationClassroom(models.Model):
    application = models.ForeignKey(
        SimulationApplication,
        verbose_name="aplicação",
        on_delete=models.CASCADE,
        related_name="application_classrooms",
    )
    classroom = models.ForeignKey(
        Classroom,
        verbose_name="turma",
        on_delete=models.PROTECT,
        related_name="simulation_applications",
    )
    applicators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="aplicadores",
        related_name="assigned_application_classrooms",
        blank=True,
        limit_choices_to={
            "role": "APPLICATOR",
            "is_active": True,
        },
    )
    room_name = models.CharField(
        "sala/local da aplicação",
        max_length=100,
        blank=True,
    )
    notes = models.TextField(
        "orientações da turma",
        blank=True,
    )
    is_active = models.BooleanField(
        "ativa",
        default=True,
    )
    created_at = models.DateTimeField(
        "adicionada em",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "turma da aplicação"
        verbose_name_plural = "turmas da aplicação"
        ordering = [
            "classroom__school__name",
            "classroom__grade__order",
            "classroom__name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["application", "classroom"],
                name="unique_classroom_by_application",
            )
        ]

    def clean(self):
        if not self.application_id or not self.classroom_id:
            return

        if (
            self.classroom.school.municipality_id
            != self.application.municipality_id
        ):
            raise ValidationError(
                {
                    "classroom": (
                        "A turma precisa pertencer ao município "
                        "da aplicação."
                    )
                }
            )

        if not self.application.assessment.grades.filter(
            pk=self.classroom.grade_id,
        ).exists():
            raise ValidationError(
                {
                    "classroom": (
                        "A série desta turma não está contemplada "
                        "pela prova selecionada."
                    )
                }
            )

        if (
            self.classroom.academic_year_id
            != self.application.assessment.academic_year_id
        ):
            raise ValidationError(
                {
                    "classroom": (
                        "O ano letivo da turma deve ser o mesmo "
                        "da prova."
                    )
                }
            )

    #def save(self, *args, **kwargs):
    #    self.full_clean()
    #    super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.application.code} — {self.classroom}"


class Participation(models.Model):
    class Status(models.TextChoices):
        EXPECTED = "EXPECTED", "Previsto"
        PRESENT = "PRESENT", "Presente"
        ABSENT = "ABSENT", "Ausente"
        ANSWER_SHEET_RECEIVED = (
            "ANSWER_SHEET_RECEIVED",
            "Gabarito recebido",
        )
        PROCESSED = "PROCESSED", "Processado"
        CANCELLED = "CANCELLED", "Cancelado"

    application = models.ForeignKey(
        SimulationApplication,
        verbose_name="aplicação",
        on_delete=models.CASCADE,
        related_name="participations",
    )
    application_classroom = models.ForeignKey(
        ApplicationClassroom,
        verbose_name="turma da aplicação",
        on_delete=models.PROTECT,
        related_name="participations",
    )
    student = models.ForeignKey(
        Student,
        verbose_name="aluno",
        on_delete=models.PROTECT,
        related_name="simulation_participations",
    )
    enrollment = models.ForeignKey(
        Enrollment,
        verbose_name="matrícula",
        on_delete=models.PROTECT,
        related_name="simulation_participations",
    )
    assessment_version = models.ForeignKey(
        AssessmentVersion,
        verbose_name="versão da prova",
        on_delete=models.PROTECT,
        related_name="participations",
    )
    card_code = models.UUIDField(
        "código seguro do cartão",
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    sequence_number = models.PositiveIntegerField(
        "número sequencial",
        null=True,
        blank=True,
    )
    status = models.CharField(
        "situação",
        max_length=30,
        choices=Status.choices,
        default=Status.EXPECTED,
    )
    notes = models.CharField(
        "observações",
        max_length=255,
        blank=True,
    )
    created_at = models.DateTimeField(
        "criada em",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "atualizada em",
        auto_now=True,
    )

    class Meta:
        verbose_name = "participação"
        verbose_name_plural = "participações"
        ordering = [
            "application",
            "application_classroom",
            "student__full_name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["application", "student"],
                name="unique_student_by_application",
            ),
            models.UniqueConstraint(
                fields=["application", "sequence_number"],
                name="unique_sequence_by_application",
            ),
        ]
        indexes = [
            models.Index(
                fields=["card_code"],
                name="participation_card_idx",
            ),
            models.Index(
                fields=["application", "status"],
                name="participation_status_idx",
            ),
        ]

    def clean(self):
        errors = {}

        if (
            self.application_classroom_id
            and self.application_id
            and self.application_classroom.application_id
            != self.application_id
        ):
            errors["application_classroom"] = (
                "A turma selecionada não pertence a esta aplicação."
            )

        if self.enrollment_id and self.student_id:
            if self.enrollment.student_id != self.student_id:
                errors["enrollment"] = (
                    "A matrícula não pertence ao aluno selecionado."
                )

        if (
            self.enrollment_id
            and self.application_classroom_id
            and self.enrollment.classroom_id
            != self.application_classroom.classroom_id
        ):
            errors["enrollment"] = (
                "A matrícula não pertence à turma da aplicação."
            )

        if (
            self.assessment_version_id
            and self.application_id
            and self.assessment_version.assessment_id
            != self.application.assessment_id
        ):
            errors["assessment_version"] = (
                "A versão não pertence à prova desta aplicação."
            )

        if (
            self.assessment_version_id
            and not self.assessment_version.is_active
        ):
            errors["assessment_version"] = (
                "A versão selecionada não está ativa."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.sequence_number and self.application_id:
            last_sequence = (
                Participation.objects.filter(
                    application_id=self.application_id,
                )
                .order_by("-sequence_number")
                .values_list("sequence_number", flat=True)
                .first()
                or 0
            )

            self.sequence_number = last_sequence + 1

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def short_card_code(self):
        return str(self.card_code).split("-")[0].upper()

    def __str__(self):
        return (
            f"{self.application.code} — "
            f"{self.student.full_name} — "
            f"Versão {self.assessment_version.code}"
        )