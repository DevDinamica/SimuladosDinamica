import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from academics.models import Classroom, Enrollment, Student
from assessments.models import (
    Assessment,
    AssessmentVersion,
    Question,
)
from institutions.models import Municipality
from requests_app.models import SimulationRequest

from django.core.validators import (
    FileExtensionValidator,
)

def default_card_portal_expiry():
    return timezone.now() + timedelta(
        days=30
    )


def validate_answer_sheet_image(file):
    maximum_size = 12 * 1024 * 1024

    if file.size > maximum_size:
        raise ValidationError(
            "A imagem não pode ultrapassar 12 MB."
        )


def answer_sheet_image_path(
    instance,
    filename,
):
    extension = Path(
        filename
    ).suffix.lower()

    application_code = (
        instance.portal.application.code
    )

    identifier = uuid.uuid4().hex

    return (
        "private/answer_sheets/"
        f"{application_code}/"
        f"{timezone.now():%Y/%m}/"
        f"{identifier}{extension}"
    )

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


class ApplicationAssessment(models.Model):
    application = models.ForeignKey(
        SimulationApplication,
        verbose_name="aplicação",
        on_delete=models.CASCADE,
        related_name="application_assessments",
    )
    assessment = models.ForeignKey(
        Assessment,
        verbose_name="prova",
        on_delete=models.PROTECT,
        related_name="application_links",
    )
    order = models.PositiveSmallIntegerField(
        "ordem",
        default=1,
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
        verbose_name = "prova da aplicação"
        verbose_name_plural = "provas da aplicação"
        ordering = [
            "application",
            "order",
            "assessment__title",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "application",
                    "assessment",
                ],
                name="unique_assessment_by_application",
            ),
            models.UniqueConstraint(
                fields=[
                    "application",
                    "order",
                ],
                name="unique_assessment_order_by_app",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "application",
                    "is_active",
                ],
                name="app_assessment_active_idx",
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
                "A prova precisa estar publicada."
            )

        if (
            self.assessment_id
            and self.application_id
            and self.assessment.academic_year_id
            != self.application.assessment.academic_year_id
        ):
            errors["assessment"] = (
                "Todas as provas da aplicação devem "
                "pertencer ao mesmo ano letivo."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def subject_name(self):
        return self.assessment.subject_names

    def __str__(self):
        return (
            f"{self.application.code} — "
            f"{self.assessment.title}"
        )

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

class ParticipationCard(models.Model):
    class Status(models.TextChoices):
        EXPECTED = (
            "EXPECTED",
            "Aguardando cartão",
        )
        RECEIVED = (
            "RECEIVED",
            "Cartão recebido",
        )
        PROCESSED = (
            "PROCESSED",
            "Processado",
        )
        CANCELLED = (
            "CANCELLED",
            "Cancelado",
        )

    participation = models.ForeignKey(
        Participation,
        verbose_name="participação",
        on_delete=models.CASCADE,
        related_name="discipline_cards",
    )
    application_assessment = models.ForeignKey(
        ApplicationAssessment,
        verbose_name="prova da aplicação",
        on_delete=models.PROTECT,
        related_name="participation_cards",
    )
    assessment_version = models.ForeignKey(
        AssessmentVersion,
        verbose_name="versão da prova",
        on_delete=models.PROTECT,
        related_name="participation_cards",
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
        max_length=20,
        choices=Status.choices,
        default=Status.EXPECTED,
    )
    created_at = models.DateTimeField(
        "criado em",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "atualizado em",
        auto_now=True,
    )

    class Meta:
        verbose_name = "cartão disciplinar"
        verbose_name_plural = "cartões disciplinares"
        ordering = [
            "participation",
            "application_assessment__order",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "participation",
                    "application_assessment",
                ],
                name="unique_card_by_participation_assessment",
            ),
            models.UniqueConstraint(
                fields=[
                    "application_assessment",
                    "sequence_number",
                ],
                name="unique_card_sequence_by_assessment",
            ),
        ]
        indexes = [
            models.Index(
                fields=["card_code"],
                name="part_card_code_idx",
            ),
            models.Index(
                fields=[
                    "application_assessment",
                    "status",
                ],
                name="part_card_status_idx",
            ),
        ]

    def clean(self):
        errors = {}

        if (
            self.participation_id
            and self.application_assessment_id
            and self.participation.application_id
            != self.application_assessment.application_id
        ):
            errors["application_assessment"] = (
                "A prova não pertence à aplicação "
                "desta participação."
            )

        if (
            self.assessment_version_id
            and self.application_assessment_id
            and self.assessment_version.assessment_id
            != self.application_assessment.assessment_id
        ):
            errors["assessment_version"] = (
                "A versão não pertence à prova selecionada."
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
        if (
            not self.sequence_number
            and self.application_assessment_id
        ):
            last_sequence = (
                ParticipationCard.objects.filter(
                    application_assessment_id=(
                        self.application_assessment_id
                    ),
                )
                .order_by("-sequence_number")
                .values_list(
                    "sequence_number",
                    flat=True,
                )
                .first()
                or 0
            )

            self.sequence_number = last_sequence + 1

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def short_card_code(self):
        return str(
            self.card_code
        ).split("-")[0].upper()

    @property
    def subject_name(self):
        return (
            self.application_assessment
            .assessment
            .subject_names
        )

    def __str__(self):
        return (
            f"{self.participation.student.full_name} — "
            f"{self.subject_name} — "
            f"Versão {self.assessment_version.code}"
        )

class CardSubmissionPortal(models.Model):
    application = models.OneToOneField(
        SimulationApplication,
        verbose_name="aplicação",
        on_delete=models.CASCADE,
        related_name="card_submission_portal",
    )
    token = models.UUIDField(
        "token de acesso",
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    contact_name = models.CharField(
        "responsável pelo envio",
        max_length=200,
        blank=True,
    )
    contact_email = models.EmailField(
        "e-mail do responsável",
        blank=True,
    )
    expires_at = models.DateTimeField(
        "válido até",
        default=default_card_portal_expiry,
    )
    is_active = models.BooleanField(
        "ativo",
        default=True,
    )
    instructions = models.TextField(
        "orientações",
        blank=True,
    )
    created_at = models.DateTimeField(
        "criado em",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "atualizado em",
        auto_now=True,
    )

    class Meta:
        verbose_name = "portal de envio de cartões"
        verbose_name_plural = (
            "portais de envio de cartões"
        )
        ordering = [
            "-created_at",
        ]
        indexes = [
            models.Index(
                fields=["token"],
                name="card_portal_token_idx",
            ),
            models.Index(
                fields=[
                    "is_active",
                    "expires_at",
                ],
                name="card_portal_access_idx",
            ),
        ]

    @property
    def is_expired(self):
        return (
            timezone.now()
            > self.expires_at
        )

    @property
    def can_be_accessed(self):
        return (
            self.is_active
            and not self.is_expired
            and self.application.status
            != SimulationApplication.Status.CANCELLED
        )

    @property
    def submission_count(self):
        return self.submissions.count()

    def __str__(self):
        return (
            f"{self.application.code} — "
            "Envio de cartões"
        )


class AnswerSheetImageSubmission(models.Model):
    class Status(models.TextChoices):
        RECEIVED = (
            "RECEIVED",
            "Recebido",
        )
        UNDER_REVIEW = (
            "UNDER_REVIEW",
            "Em revisão",
        )
        ACCEPTED = (
            "ACCEPTED",
            "Aceito",
        )
        REJECTED = (
            "REJECTED",
            "Rejeitado",
        )

    portal = models.ForeignKey(
        CardSubmissionPortal,
        verbose_name="portal",
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    participation = models.ForeignKey(
        Participation,
        verbose_name="participação",
        on_delete=models.PROTECT,
        related_name="image_submissions",
    )
    participation_card = models.ForeignKey(
        ParticipationCard,
        verbose_name="cartão disciplinar",
        on_delete=models.PROTECT,
        related_name="image_submissions",
        null=True,
        blank=True,
    )
    submission_code = models.UUIDField(
        "código do envio",
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    image = models.ImageField(
        "imagem do cartão-resposta",
        upload_to=answer_sheet_image_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "jpg",
                    "jpeg",
                    "png",
                    "webp",
                ],
                message=(
                    "Envie uma imagem JPG, PNG "
                    "ou WEBP."
                ),
            ),
            validate_answer_sheet_image,
        ],
    )
    original_name = models.CharField(
        "nome original",
        max_length=255,
        blank=True,
    )
    file_size = models.PositiveIntegerField(
        "tamanho do arquivo",
        default=0,
        editable=False,
    )
    status = models.CharField(
        "situação",
        max_length=30,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    sender_name = models.CharField(
        "nome de quem enviou",
        max_length=200,
        blank=True,
    )
    review_notes = models.TextField(
        "observações da revisão",
        blank=True,
    )
    created_at = models.DateTimeField(
        "recebido em",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "atualizado em",
        auto_now=True,
    )

    class Meta:
        verbose_name = "cartão fotografado"
        verbose_name_plural = (
            "cartões fotografados"
        )
        ordering = [
            "-created_at",
        ]
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="sheet_upload_status_idx",
            ),
            models.Index(
                fields=["submission_code"],
                name="sheet_upload_code_idx",
            ),
        ]

    @property
    def protocol(self):
        short_code = str(
            self.submission_code
        ).split("-")[0].upper()

        return f"ENV-{short_code}"

    def clean(self):
        errors = {}

        if (
            self.portal_id
            and self.participation_id
            and self.participation.application_id
            != self.portal.application_id
        ):
            errors["participation"] = (
                "O aluno não pertence à aplicação "
                "deste portal."
            )

        if (
            self.participation_id
            and self.participation.status
            in {
                Participation.Status.ABSENT,
                Participation.Status.CANCELLED,
            }
        ):
            errors["participation"] = (
                "Não é possível enviar cartão para "
                "participação ausente ou cancelada."
            )
        
        if (
            self.participation_card_id
            and self.participation_id
            and self.participation_card.participation_id
            != self.participation_id
        ):
            errors["participation_card"] = (
                "O cartão selecionado não pertence "
                "ao aluno informado."
            )

        if (
            self.participation_card_id
            and self.portal_id
            and (
                self.participation_card
                .participation
                .application_id
                != self.portal.application_id
            )
        ):
            errors["participation_card"] = (
                "O cartão não pertence à aplicação "
                "deste portal."
            )

        if (
            self.participation_card_id
            and self.participation_card.status
            == ParticipationCard.Status.CANCELLED
        ):
            errors["participation_card"] = (
                "Não é possível enviar uma imagem "
                "para um cartão cancelado."
            )

        if errors:
            raise ValidationError(
                errors
            )

    def save(self, *args, **kwargs):
        if self.image:
            if not self.original_name:
                self.original_name = Path(
                    self.image.name
                ).name

            try:
                self.file_size = (
                    self.image.size
                )
            except (AttributeError, OSError):
                pass

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.protocol} — "
            f"{self.participation.student.full_name}"
        )

class AnswerSheet(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Em digitação"
        ENTERED = "ENTERED", "Digitado"
        VALIDATED = "VALIDATED", "Validado"
        PROCESSED = "PROCESSED", "Processado"
        REVIEW_REQUIRED = (
            "REVIEW_REQUIRED",
            "Revisão necessária",
        )

    class InputMethod(models.TextChoices):
        MANUAL = "MANUAL", "Digitação manual"
        CAMERA = "CAMERA", "Leitura pela câmera"
        IMPORT = "IMPORT", "Importação"

    participation = models.OneToOneField(
        Participation,
        verbose_name="participação",
        on_delete=models.CASCADE,
        related_name="answer_sheet",
    )
    status = models.CharField(
        "situação",
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    input_method = models.CharField(
        "forma de lançamento",
        max_length=20,
        choices=InputMethod.choices,
        default=InputMethod.MANUAL,
    )
    question_count = models.PositiveSmallIntegerField(
        "quantidade de questões",
        default=0,
    )
    answered_count = models.PositiveSmallIntegerField(
        "questões respondidas",
        default=0,
    )
    blank_count = models.PositiveSmallIntegerField(
        "questões em branco",
        default=0,
    )
    multiple_count = models.PositiveSmallIntegerField(
        "marcações múltiplas",
        default=0,
    )
    correct_count = models.PositiveSmallIntegerField(
        "acertos",
        default=0,
    )
    incorrect_count = models.PositiveSmallIntegerField(
        "erros",
        default=0,
    )
    score = models.DecimalField(
        "nota",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    percentage = models.DecimalField(
        "percentual",
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="digitado por",
        on_delete=models.SET_NULL,
        related_name="entered_answer_sheets",
        null=True,
        blank=True,
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validado por",
        on_delete=models.SET_NULL,
        related_name="validated_answer_sheets",
        null=True,
        blank=True,
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="processado por",
        on_delete=models.SET_NULL,
        related_name="processed_answer_sheets",
        null=True,
        blank=True,
    )
    entered_at = models.DateTimeField(
        "digitado em",
        null=True,
        blank=True,
    )
    validated_at = models.DateTimeField(
        "validado em",
        null=True,
        blank=True,
    )
    processed_at = models.DateTimeField(
        "processado em",
        null=True,
        blank=True,
    )
    processing_message = models.CharField(
        "mensagem de processamento",
        max_length=255,
        blank=True,
    )
    created_at = models.DateTimeField(
        "criado em",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "atualizado em",
        auto_now=True,
    )

    class Meta:
        verbose_name = "cartão lançado"
        verbose_name_plural = "cartões lançados"
        ordering = [
            "-participation__application__application_date",
            "participation__sequence_number",
        ]
        indexes = [
            models.Index(
                fields=["status"],
                name="answer_sheet_status_idx",
            ),
            models.Index(
                fields=["processed_at"],
                name="answer_sheet_processed_idx",
            ),
        ]

    @property
    def assessment_version(self):
        return self.participation.assessment_version

    @property
    def student(self):
        return self.participation.student

    def clean(self):
        if not self.participation_id:
            return

        if self.participation.status in {
            Participation.Status.ABSENT,
            Participation.Status.CANCELLED,
        }:
            raise ValidationError(
                {
                    "participation": (
                        "Não é possível lançar respostas para uma "
                        "participação ausente ou cancelada."
                    )
                }
            )

    def __str__(self):
        return (
            f"{self.participation.application.code} — "
            f"{self.participation.student.full_name}"
        )

class AnswerEntry(models.Model):
    class MarkingStatus(models.TextChoices):
        SINGLE = "SINGLE", "Uma alternativa"
        BLANK = "BLANK", "Em branco"
        MULTIPLE = "MULTIPLE", "Marcação múltipla"

    answer_sheet = models.ForeignKey(
        AnswerSheet,
        verbose_name="cartão lançado",
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        Question,
        verbose_name="questão",
        on_delete=models.PROTECT,
        related_name="answer_entries",
    )
    marking_status = models.CharField(
        "tipo de marcação",
        max_length=20,
        choices=MarkingStatus.choices,
        default=MarkingStatus.BLANK,
    )
    selected_answer = models.CharField(
        "alternativa marcada",
        max_length=1,
        choices=Question.Answer.choices,
        blank=True,
    )
    is_correct = models.BooleanField(
        "correta",
        null=True,
        blank=True,
    )
    awarded_score = models.DecimalField(
        "pontuação obtida",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
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
        verbose_name = "resposta lançada"
        verbose_name_plural = "respostas lançadas"
        ordering = [
            "answer_sheet",
            "question__number",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["answer_sheet", "question"],
                name="unique_question_by_answer_sheet",
            )
        ]
        indexes = [
            models.Index(
                fields=["answer_sheet", "marking_status"],
                name="answer_entry_sheet_mark_idx",
            ),
            models.Index(
                fields=["question", "is_correct"],
                name="ans_entry_question_result_idx",
            ),
        ]

    def clean(self):
        errors = {}

        if self.answer_sheet_id and self.question_id:
            expected_version_id = (
                self.answer_sheet
                .participation
                .assessment_version_id
            )

            if self.question.version_id != expected_version_id:
                errors["question"] = (
                    "A questão não pertence à versão atribuída "
                    "a este participante."
                )

        if self.marking_status == self.MarkingStatus.SINGLE:
            if not self.selected_answer:
                errors["selected_answer"] = (
                    "Informe a alternativa para uma marcação simples."
                )
            elif self.question_id:
                allowed_answers = list("ABCDE")[
                    : self.question.version.option_count
                ]

                if self.selected_answer not in allowed_answers:
                    errors["selected_answer"] = (
                        "A alternativa não existe nesta versão."
                    )
        elif self.selected_answer:
            errors["selected_answer"] = (
                "Questões em branco ou com marcação múltipla "
                "não podem possuir uma alternativa única."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.marking_status == self.MarkingStatus.SINGLE:
            result = self.selected_answer
        else:
            result = self.get_marking_status_display()

        return (
            f"Questão {self.question.number}: {result}"
        )


class AnswerSheetBreakdown(models.Model):
    class Dimension(models.TextChoices):
        COMPONENT = "COMPONENT", "Componente curricular"
        DESCRIPTOR = "DESCRIPTOR", "Habilidade/descritor"

    answer_sheet = models.ForeignKey(
        AnswerSheet,
        verbose_name="cartão lançado",
        on_delete=models.CASCADE,
        related_name="breakdowns",
    )
    dimension = models.CharField(
        "dimensão",
        max_length=20,
        choices=Dimension.choices,
    )
    key = models.CharField(
        "identificador",
        max_length=100,
    )
    label = models.CharField(
        "descrição",
        max_length=255,
    )
    question_count = models.PositiveSmallIntegerField(
        "quantidade de questões",
        default=0,
    )
    answered_count = models.PositiveSmallIntegerField(
        "respondidas",
        default=0,
    )
    correct_count = models.PositiveSmallIntegerField(
        "acertos",
        default=0,
    )
    incorrect_count = models.PositiveSmallIntegerField(
        "erros",
        default=0,
    )
    blank_count = models.PositiveSmallIntegerField(
        "em branco",
        default=0,
    )
    multiple_count = models.PositiveSmallIntegerField(
        "marcações múltiplas",
        default=0,
    )
    score = models.DecimalField(
        "pontuação",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    maximum_score = models.DecimalField(
        "pontuação máxima",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    percentage = models.DecimalField(
        "percentual",
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        verbose_name = "resultado detalhado"
        verbose_name_plural = "resultados detalhados"
        ordering = [
            "answer_sheet",
            "dimension",
            "key",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "answer_sheet",
                    "dimension",
                    "key",
                ],
                name="unique_breakdown_by_answer_sheet",
            )
        ]
        indexes = [
            models.Index(
                fields=["dimension", "key"],
                name="answer_breakdown_dimension_idx",
            )
        ]

    def __str__(self):
        return (
            f"{self.answer_sheet} — "
            f"{self.get_dimension_display()}: {self.label}"
        )