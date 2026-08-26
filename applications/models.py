import uuid
from decimal import Decimal
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