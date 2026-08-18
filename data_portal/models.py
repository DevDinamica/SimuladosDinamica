import uuid
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from applications.models import SimulationApplication


def default_portal_expiry():
    return timezone.now() + timedelta(days=15)


def validate_spreadsheet_file(file):
    extension = Path(file.name).suffix.lower()

    if extension != ".xlsx":
        raise ValidationError(
            "Envie uma planilha no formato .xlsx."
        )

    maximum_size = 5 * 1024 * 1024

    if file.size > maximum_size:
        raise ValidationError(
            "A planilha não pode ultrapassar 5 MB."
        )


class DataPreparationPortal(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aguardando dados"
        IN_PROGRESS = "IN_PROGRESS", "Em preenchimento"
        FILE_RECEIVED = "FILE_RECEIVED", "Arquivo recebido"
        HAS_ERRORS = "HAS_ERRORS", "Com pendências"
        READY = "READY", "Dados validados"
        SUBMITTED = "SUBMITTED", "Enviado para revisão"
        IMPORTED = "IMPORTED", "Importado"
        CLOSED = "CLOSED", "Encerrado"

    application = models.OneToOneField(
        SimulationApplication,
        verbose_name="aplicação",
        on_delete=models.CASCADE,
        related_name="data_portal",
    )
    token = models.UUIDField(
        "token",
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    contact_name = models.CharField(
        "responsável institucional",
        max_length=200,
    )
    contact_email = models.EmailField(
        "e-mail do responsável",
    )
    expires_at = models.DateTimeField(
        "válido até",
        default=default_portal_expiry,
    )
    status = models.CharField(
        "situação",
        max_length=30,
        choices=Status.choices,
        default=Status.OPEN,
    )
    is_active = models.BooleanField(
        "ativo",
        default=True,
    )
    submitted_at = models.DateTimeField(
        "enviado para revisão em",
        null=True,
        blank=True,
    )
    imported_at = models.DateTimeField(
        "importado em",
        null=True,
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
        verbose_name = "portal de preparação"
        verbose_name_plural = "portais de preparação"
        ordering = ["-created_at"]

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def can_be_accessed(self):
        return (
            self.is_active
            and not self.is_expired
            and self.status
            not in {
                self.Status.IMPORTED,
                self.Status.CLOSED,
            }
        )

    @property
    def latest_upload(self):
        return self.uploads.order_by(
            "-created_at"
        ).first()

    def __str__(self):
        return (
            f"{self.application.code} — "
            f"{self.contact_name}"
        )


class SpreadsheetUpload(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Recebido"
        VALID = "VALID", "Válido"
        INVALID = "INVALID", "Com erros"
        IMPORTED = "IMPORTED", "Importado"

    portal = models.ForeignKey(
        DataPreparationPortal,
        verbose_name="portal",
        on_delete=models.CASCADE,
        related_name="uploads",
    )
    file = models.FileField(
        "planilha",
        upload_to="private/student_imports/%Y/%m/",
        validators=[validate_spreadsheet_file],
    )
    original_name = models.CharField(
        "nome original",
        max_length=255,
        blank=True,
    )
    status = models.CharField(
        "situação",
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    school_count = models.PositiveIntegerField(
        "escolas encontradas",
        default=0,
    )
    classroom_count = models.PositiveIntegerField(
        "turmas encontradas",
        default=0,
    )
    student_count = models.PositiveIntegerField(
        "alunos encontrados",
        default=0,
    )
    error_count = models.PositiveIntegerField(
        "quantidade de erros",
        default=0,
    )
    warning_count = models.PositiveIntegerField(
        "quantidade de avisos",
        default=0,
    )
    validation_report = models.JSONField(
        "relatório da validação",
        default=dict,
        blank=True,
    )
    created_at = models.DateTimeField(
        "recebido em",
        auto_now_add=True,
    )
    imported_at = models.DateTimeField(
        "importado em",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "planilha recebida"
        verbose_name_plural = "planilhas recebidas"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.file and not self.original_name:
            self.original_name = self.file.name.split("/")[-1]

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.portal.application.code} — "
            f"{self.original_name}"
        )