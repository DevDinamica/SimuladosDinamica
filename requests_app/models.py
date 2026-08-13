from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from academics.models import Grade, Subject


class SimulationRequest(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Recebida"
        UNDER_REVIEW = "UNDER_REVIEW", "Em análise"
        WAITING_INFORMATION = (
            "WAITING_INFORMATION",
            "Aguardando informações",
        )
        APPROVED = "APPROVED", "Aprovada"
        PREPARING_DATA = "PREPARING_DATA", "Preparando dados"
        APPLICATION_CREATED = (
            "APPLICATION_CREATED",
            "Aplicação criada",
        )
        CANCELLED = "CANCELLED", "Cancelada"
        COMPLETED = "COMPLETED", "Concluída"

    class RequestScope(models.TextChoices):
        MUNICIPAL_NETWORK = (
            "MUNICIPAL_NETWORK",
            "Rede municipal",
        )
        SINGLE_SCHOOL = (
            "SINGLE_SCHOOL",
            "Uma escola",
        )
        SCHOOL_GROUP = (
            "SCHOOL_GROUP",
            "Conjunto de escolas",
        )
        SPECIFIC_CLASSROOMS = (
            "SPECIFIC_CLASSROOMS",
            "Turmas específicas",
        )

    class AssessmentObjective(models.TextChoices):
        INITIAL_DIAGNOSIS = (
            "INITIAL_DIAGNOSIS",
            "Diagnóstico inicial",
        )
        MONITORING = (
            "MONITORING",
            "Acompanhamento da aprendizagem",
        )
        FINAL_ASSESSMENT = (
            "FINAL_ASSESSMENT",
            "Avaliação final",
        )
        EXTERNAL_PREPARATION = (
            "EXTERNAL_PREPARATION",
            "Preparação para avaliação externa",
        )
        OTHER = "OTHER", "Outro"

    class AssessmentSource(models.TextChoices):
        PUBLISHER = (
            "PUBLISHER",
            "Prova fornecida pela Editora Dinâmica",
        )
        REQUESTER = (
            "REQUESTER",
            "Prova fornecida pela instituição solicitante",
        )
        TO_DEFINE = (
            "TO_DEFINE",
            "A definir",
        )

    class PrintResponsibility(models.TextChoices):
        PUBLISHER = (
            "PUBLISHER",
            "Editora Dinâmica",
        )
        REQUESTER = (
            "REQUESTER",
            "Município ou escola",
        )
        TO_DEFINE = (
            "TO_DEFINE",
            "A definir",
        )

    class ApplicatorResponsibility(models.TextChoices):
        PUBLISHER = (
            "PUBLISHER",
            "Aplicadores da Editora Dinâmica",
        )
        REQUESTER = (
            "REQUESTER",
            "Aplicadores locais",
        )
        SHARED = (
            "SHARED",
            "Operação compartilhada",
        )
        TO_DEFINE = (
            "TO_DEFINE",
            "A definir",
        )

    class InternetQuality(models.TextChoices):
        GOOD = "GOOD", "Boa"
        LIMITED = "LIMITED", "Limitada"
        UNAVAILABLE = "UNAVAILABLE", "Sem internet"
        UNKNOWN = "UNKNOWN", "Não informado"

    protocol = models.CharField(
        "protocolo",
        max_length=30,
        unique=True,
        blank=True,
        editable=False,
    )

    requester_name = models.CharField(
        "nome do responsável",
        max_length=200,
    )
    requester_role = models.CharField(
        "cargo ou função",
        max_length=150,
    )
    requester_email = models.EmailField(
        "e-mail institucional",
    )
    requester_phone = models.CharField(
        "telefone/WhatsApp",
        max_length=20,
    )
    requester_institution = models.CharField(
        "instituição solicitante",
        max_length=200,
    )

    state = models.CharField(
        "estado",
        max_length=2,
        default="CE",
    )
    municipality_name = models.CharField(
        "município",
        max_length=150,
    )
    request_scope = models.CharField(
        "abrangência",
        max_length=30,
        choices=RequestScope.choices,
    )
    education_department_name = models.CharField(
        "Secretaria de Educação",
        max_length=200,
        blank=True,
    )
    school_name = models.CharField(
        "escola de referência",
        max_length=200,
        blank=True,
    )
    school_inep_code = models.CharField(
        "código INEP",
        max_length=20,
        blank=True,
    )

    preferred_date = models.DateField(
        "data desejada",
    )
    alternative_date = models.DateField(
        "data alternativa",
        null=True,
        blank=True,
    )
    academic_year = models.PositiveIntegerField(
        "ano letivo",
        default=timezone.now().year,
    )
    grades = models.ManyToManyField(
        Grade,
        verbose_name="séries/anos",
        related_name="simulation_requests",
    )
    subjects = models.ManyToManyField(
        Subject,
        verbose_name="disciplinas",
        related_name="simulation_requests",
    )
    estimated_school_count = models.PositiveIntegerField(
        "quantidade estimada de escolas",
        default=1,
        validators=[MinValueValidator(1)],
    )
    estimated_classroom_count = models.PositiveIntegerField(
        "quantidade estimada de turmas",
        default=1,
        validators=[MinValueValidator(1)],
    )
    estimated_student_count = models.PositiveIntegerField(
        "quantidade estimada de alunos",
        validators=[MinValueValidator(1)],
    )
    estimated_question_count = models.PositiveIntegerField(
        "quantidade estimada de questões",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    objective = models.CharField(
        "objetivo da avaliação",
        max_length=30,
        choices=AssessmentObjective.choices,
    )
    objective_details = models.CharField(
        "detalhamento do objetivo",
        max_length=255,
        blank=True,
    )

    assessment_source = models.CharField(
        "origem da prova",
        max_length=20,
        choices=AssessmentSource.choices,
        default=AssessmentSource.TO_DEFINE,
    )
    print_responsibility = models.CharField(
        "responsável pela impressão",
        max_length=20,
        choices=PrintResponsibility.choices,
        default=PrintResponsibility.TO_DEFINE,
    )
    applicator_responsibility = models.CharField(
        "responsável pela aplicação",
        max_length=20,
        choices=ApplicatorResponsibility.choices,
        default=ApplicatorResponsibility.TO_DEFINE,
    )
    has_scanning_devices = models.BooleanField(
        "possui celulares para digitalização",
        default=False,
    )
    internet_quality = models.CharField(
        "qualidade da internet",
        max_length=20,
        choices=InternetQuality.choices,
        default=InternetQuality.UNKNOWN,
    )
    notes = models.TextField(
        "observações",
        blank=True,
    )

    privacy_accepted = models.BooleanField(
        "aceite institucional e de privacidade",
        default=False,
    )
    privacy_accepted_at = models.DateTimeField(
        "aceite realizado em",
        null=True,
        blank=True,
        editable=False,
    )

    status = models.CharField(
        "situação",
        max_length=30,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    internal_notes = models.TextField(
        "observações internas",
        blank=True,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="responsável interno",
        on_delete=models.SET_NULL,
        related_name="assigned_simulation_requests",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        "recebida em",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "atualizada em",
        auto_now=True,
    )

    class Meta:
        verbose_name = "solicitação de simulado"
        verbose_name_plural = "solicitações de simulados"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["protocol"],
                name="request_protocol_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="request_status_date_idx",
            ),
            models.Index(
                fields=["municipality_name"],
                name="request_municipality_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        new_request = self.pk is None

        if new_request and self.privacy_accepted:
            self.privacy_accepted_at = timezone.now()

        super().save(*args, **kwargs)

        if not self.protocol:
            self.protocol = (
                f"SOL-{self.created_at.year}-{self.pk:06d}"
            )

            type(self).objects.filter(pk=self.pk).update(
                protocol=self.protocol
            )

    @property
    def estimated_total_materials(self):
        return self.estimated_student_count

    @property
    def days_until_preferred_date(self):
        if not self.preferred_date:
            return None

        return (
            self.preferred_date - timezone.localdate()
        ).days

    def __str__(self):
        reference = self.protocol or "Nova solicitação"

        return (
            f"{reference} — "
            f"{self.requester_institution} — "
            f"{self.municipality_name}/{self.state}"
        )