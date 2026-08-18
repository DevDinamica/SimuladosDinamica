from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from academics.models import AcademicYear, Grade, Subject


class Assessment(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        PUBLISHED = "PUBLISHED", "Publicada"
        CLOSED = "CLOSED", "Encerrada"

    title = models.CharField(
        "título",
        max_length=200,
    )
    code = models.CharField(
        "código",
        max_length=50,
        unique=True,
        help_text="Exemplo: SIM-MAT-9ANO-2026.",
    )
    description = models.TextField(
        "descrição",
        blank=True,
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        verbose_name="ano letivo",
        on_delete=models.PROTECT,
        related_name="assessments",
    )
    subject = models.ForeignKey(
        Subject,
        verbose_name="disciplina principal",
        on_delete=models.PROTECT,
        related_name="assessments",
        null=True,
        blank=True,
        help_text=(
            "Utilizado em provas de uma única disciplina. "
            "Para simulados multidisciplinares, use os componentes."
        ),
    )
    grades = models.ManyToManyField(
        Grade,
        verbose_name="séries/anos",
        related_name="assessments",
    )
    instructions = models.TextField(
        "instruções",
        blank=True,
    )
    source_file = models.FileField(
        "arquivo da prova",
        upload_to="assessments/source_files/%Y/%m/",
        blank=True,
    )
    status = models.CharField(
        "situação",
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
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
        verbose_name = "prova"
        verbose_name_plural = "provas"
        ordering = ["-academic_year__year", "title"]

    @property
    def version_count(self):
        return self.versions.count()

    @property
    def subject_count(self):
        if self.components.exists():
            return (
                self.components.filter(is_active=True)
                .values("subject_id")
                .distinct()
                .count()
            )

        return 1 if self.subject_id else 0


    @property
    def subject_names(self):
        if self.components.exists():
            return ", ".join(
                self.components.filter(is_active=True)
                .order_by("order")
                .values_list("subject__name", flat=True)
            )

        if self.subject_id:
            return self.subject.name

        return "Sem disciplina"

    def __str__(self):
        return f"{self.title} — {self.academic_year}"

class AssessmentComponent(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        verbose_name="prova",
        on_delete=models.CASCADE,
        related_name="components",
    )
    subject = models.ForeignKey(
        Subject,
        verbose_name="disciplina",
        on_delete=models.PROTECT,
        related_name="assessment_components",
    )
    code = models.CharField(
        "código",
        max_length=30,
        help_text="Exemplo: PORT ou MAT.",
    )
    title = models.CharField(
        "título",
        max_length=150,
        help_text="Exemplo: Língua Portuguesa.",
    )
    start_question = models.PositiveSmallIntegerField(
        "questão inicial",
        validators=[MinValueValidator(1)],
    )
    end_question = models.PositiveSmallIntegerField(
        "questão final",
        validators=[MinValueValidator(1)],
    )
    order = models.PositiveSmallIntegerField(
        "ordem",
        default=1,
    )
    is_active = models.BooleanField(
        "ativo",
        default=True,
    )

    class Meta:
        verbose_name = "componente da prova"
        verbose_name_plural = "componentes da prova"
        ordering = ["assessment", "order", "start_question"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "code"],
                name="unique_component_code_by_assessment",
            ),
            models.UniqueConstraint(
                fields=["assessment", "order"],
                name="unique_component_order_by_assessment",
            ),
        ]

    def clean(self):
        self.code = self.code.strip().upper()

        if self.end_question < self.start_question:
            raise ValidationError(
                {
                    "end_question": (
                        "A questão final não pode ser anterior "
                        "à questão inicial."
                    )
                }
            )

        if self.assessment_id:
            overlapping_components = (
                AssessmentComponent.objects.filter(
                    assessment_id=self.assessment_id,
                    start_question__lte=self.end_question,
                    end_question__gte=self.start_question,
                )
            )

            if self.pk:
                overlapping_components = (
                    overlapping_components.exclude(pk=self.pk)
                )

            if overlapping_components.exists():
                raise ValidationError(
                    "O intervalo deste componente coincide com "
                    "outro componente da mesma prova."
                )

    @property
    def question_count(self):
        return self.end_question - self.start_question + 1

    def __str__(self):
        return (
            f"{self.assessment.title} — {self.title} "
            f"({self.start_question}–{self.end_question})"
        )


class AssessmentVersion(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        verbose_name="prova",
        on_delete=models.CASCADE,
        related_name="versions",
    )
    code = models.CharField(
        "versão",
        max_length=10,
        default="A",
        help_text="Exemplo: A, B ou C.",
    )
    question_count = models.PositiveSmallIntegerField(
        "quantidade de questões",
        validators=[MinValueValidator(1)],
    )
    option_count = models.PositiveSmallIntegerField(
        "alternativas por questão",
        default=5,
        validators=[MinValueValidator(2)],
        help_text="Use 4 para A–D ou 5 para A–E.",
    )
    total_score = models.DecimalField(
        "nota máxima",
        max_digits=6,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    source_file = models.FileField(
        "arquivo específico da versão",
        upload_to="assessments/versions/%Y/%m/",
        blank=True,
    )
    is_active = models.BooleanField(
        "ativa",
        default=True,
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
        verbose_name = "versão da prova"
        verbose_name_plural = "versões das provas"
        ordering = ["assessment", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "code"],
                name="unique_version_by_assessment",
            )
        ]

    def clean(self):
        self.code = self.code.strip().upper()

        if self.option_count > 5:
            raise ValidationError(
                {
                    "option_count": (
                        "A versão Light aceita no máximo cinco "
                        "alternativas: A, B, C, D e E."
                    )
                }
            )

    @property
    def registered_question_count(self):
        return self.questions.count()

    @property
    def is_answer_key_complete(self):
        return (
            self.question_count > 0
            and self.registered_question_count == self.question_count
            and not self.questions.filter(correct_answer="").exists()
        )

    def __str__(self):
        return f"{self.assessment.title} — Versão {self.code}"


class Question(models.Model):
    class Answer(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"
        D = "D", "D"
        E = "E", "E"

    version = models.ForeignKey(
        AssessmentVersion,
        verbose_name="versão da prova",
        on_delete=models.CASCADE,
        related_name="questions",
    )
    component = models.ForeignKey(
        AssessmentComponent,
        verbose_name="componente curricular",
        on_delete=models.PROTECT,
        related_name="questions",
        null=True,
        blank=True,
    )
    number = models.PositiveSmallIntegerField(
        "número",
        validators=[MinValueValidator(1)],
    )
    statement = models.TextField(
        "enunciado",
        blank=True,
        help_text=(
            "Opcional no modo rápido. A prova pode permanecer apenas em PDF."
        ),
    )
    descriptor_code = models.CharField(
        "código da habilidade/descritor",
        max_length=50,
        blank=True,
    )
    descriptor = models.CharField(
        "habilidade/descritor",
        max_length=255,
        blank=True,
    )
    correct_answer = models.CharField(
        "resposta correta",
        max_length=1,
        choices=Answer.choices,
        blank=True,
        help_text=(
            "Pode permanecer vazia enquanto o gabarito estiver "
            "aguardando confirmação pedagógica."
        ),
    )
    weight = models.DecimalField(
        "peso",
        max_digits=6,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    is_active = models.BooleanField(
        "ativa",
        default=True,
    )

    class Meta:
        verbose_name = "questão"
        verbose_name_plural = "questões"
        ordering = ["version", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "number"],
                name="unique_question_number_by_version",
            )
        ]

def clean(self):
    if not self.version_id:
        return

    if self.number > self.version.question_count:
        raise ValidationError(
            {
                "number": (
                    "O número da questão não pode ultrapassar "
                    "a quantidade definida na versão."
                )
            }
        )

    allowed_answers = list("ABCDE")[
        : self.version.option_count
    ]

    if (
        self.correct_answer
        and self.correct_answer not in allowed_answers
    ):
        raise ValidationError(
            {
                "correct_answer": (
                    "Essa alternativa não existe na configuração "
                    "desta versão."
                )
            }
        )

    if self.component_id:
        if (
            self.component.assessment_id
            != self.version.assessment_id
        ):
            raise ValidationError(
                {
                    "component": (
                        "O componente precisa pertencer à mesma "
                        "prova da versão."
                    )
                }
            )

        if not (
            self.component.start_question
            <= self.number
            <= self.component.end_question
        ):
            raise ValidationError(
                {
                    "component": (
                        "O número da questão está fora do intervalo "
                        "definido para este componente."
                    )
                }
            )

    @property
    def calculated_score(self):
        questions = self.version.questions.filter(
            is_active=True,
        )

        total_weight = sum(
            question.weight for question in questions
        )

        if not total_weight:
            return Decimal("0.00")

        return (
            self.weight
            / total_weight
            * self.version.total_score
        ).quantize(Decimal("0.01"))

    def __str__(self):
        return (
            f"{self.version} — Questão {self.number}: "
            f"{self.correct_answer}"
        )