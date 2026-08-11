from django.core.validators import MinValueValidator
from django.db import models

from institutions.models import School


class AcademicYear(models.Model):
    year = models.PositiveIntegerField(
        "ano",
        unique=True,
        validators=[MinValueValidator(2020)],
    )
    is_current = models.BooleanField(
        "ano atual",
        default=False,
    )
    is_active = models.BooleanField(
        "ativo",
        default=True,
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
        verbose_name = "ano letivo"
        verbose_name_plural = "anos letivos"
        ordering = ["-year"]

    def __str__(self):
        return str(self.year)


class EducationStage(models.Model):
    name = models.CharField(
        "nome",
        max_length=100,
        unique=True,
    )
    order = models.PositiveSmallIntegerField(
        "ordem",
        default=0,
    )
    is_active = models.BooleanField(
        "ativa",
        default=True,
    )

    class Meta:
        verbose_name = "etapa de ensino"
        verbose_name_plural = "etapas de ensino"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Grade(models.Model):
    stage = models.ForeignKey(
        EducationStage,
        verbose_name="etapa de ensino",
        on_delete=models.PROTECT,
        related_name="grades",
    )
    name = models.CharField(
        "nome",
        max_length=100,
    )
    code = models.CharField(
        "código",
        max_length=30,
        unique=True,
    )
    order = models.PositiveSmallIntegerField(
        "ordem",
        default=0,
    )
    is_active = models.BooleanField(
        "ativa",
        default=True,
    )

    class Meta:
        verbose_name = "série/ano"
        verbose_name_plural = "séries/anos"
        ordering = ["stage__order", "order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["stage", "name"],
                name="unique_grade_by_stage",
            )
        ]

    def __str__(self):
        return f"{self.name} — {self.stage}"


class Subject(models.Model):
    name = models.CharField(
        "nome",
        max_length=100,
        unique=True,
    )
    code = models.CharField(
        "código",
        max_length=30,
        unique=True,
    )
    is_active = models.BooleanField(
        "ativa",
        default=True,
    )

    class Meta:
        verbose_name = "disciplina"
        verbose_name_plural = "disciplinas"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Classroom(models.Model):
    class Shift(models.TextChoices):
        MORNING = "MORNING", "Manhã"
        AFTERNOON = "AFTERNOON", "Tarde"
        EVENING = "EVENING", "Noite"
        FULL_TIME = "FULL_TIME", "Integral"

    school = models.ForeignKey(
        School,
        verbose_name="escola",
        on_delete=models.PROTECT,
        related_name="classrooms",
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        verbose_name="ano letivo",
        on_delete=models.PROTECT,
        related_name="classrooms",
    )
    grade = models.ForeignKey(
        Grade,
        verbose_name="série/ano",
        on_delete=models.PROTECT,
        related_name="classrooms",
    )
    name = models.CharField(
        "identificação da turma",
        max_length=50,
        help_text="Exemplo: A, B, Única ou 901.",
    )
    shift = models.CharField(
        "turno",
        max_length=20,
        choices=Shift.choices,
        default=Shift.MORNING,
    )
    subjects = models.ManyToManyField(
        Subject,
        verbose_name="disciplinas",
        related_name="classrooms",
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
        verbose_name = "turma"
        verbose_name_plural = "turmas"
        ordering = [
            "-academic_year__year",
            "school__name",
            "grade__order",
            "name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "school",
                    "academic_year",
                    "grade",
                    "name",
                    "shift",
                ],
                name="unique_classroom_configuration",
            )
        ]

    def __str__(self):
        return (
            f"{self.grade.name} {self.name} — "
            f"{self.school.name} ({self.academic_year.year})"
        )


class Student(models.Model):
    school = models.ForeignKey(
        School,
        verbose_name="escola",
        on_delete=models.PROTECT,
        related_name="students",
    )
    registration_code = models.CharField(
        "matrícula",
        max_length=50,
    )
    full_name = models.CharField(
        "nome completo",
        max_length=200,
    )
    birth_date = models.DateField(
        "data de nascimento",
        null=True,
        blank=True,
    )
    responsible_name = models.CharField(
        "nome do responsável",
        max_length=200,
        blank=True,
    )
    responsible_phone = models.CharField(
        "telefone do responsável",
        max_length=20,
        blank=True,
    )
    is_active = models.BooleanField(
        "ativo",
        default=True,
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
        verbose_name = "aluno"
        verbose_name_plural = "alunos"
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "registration_code"],
                name="unique_student_registration_by_school",
            )
        ]
        indexes = [
            models.Index(
                fields=["full_name"],
                name="student_name_idx",
            ),
            models.Index(
                fields=["registration_code"],
                name="student_registration_idx",
            ),
        ]

    @property
    def municipality(self):
        return self.school.municipality

    def __str__(self):
        return f"{self.full_name} — {self.registration_code}"


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Ativa"
        TRANSFERRED = "TRANSFERRED", "Transferido"
        CANCELLED = "CANCELLED", "Cancelada"
        COMPLETED = "COMPLETED", "Concluída"

    student = models.ForeignKey(
        Student,
        verbose_name="aluno",
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    classroom = models.ForeignKey(
        Classroom,
        verbose_name="turma",
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    status = models.CharField(
        "situação",
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    enrollment_date = models.DateField(
        "data da matrícula",
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
        verbose_name = "matrícula"
        verbose_name_plural = "matrículas"
        ordering = [
            "-classroom__academic_year__year",
            "student__full_name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "classroom"],
                name="unique_student_classroom_enrollment",
            )
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if (
            self.student_id
            and self.classroom_id
            and self.student.school_id != self.classroom.school_id
        ):
            raise ValidationError(
                {
                    "classroom": (
                        "A turma precisa pertencer à mesma escola do aluno."
                    )
                }
            )

    def __str__(self):
        return f"{self.student} — {self.classroom}"