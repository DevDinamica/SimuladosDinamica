from django.contrib.auth.models import AbstractUser
from django.db import models

from institutions.models import Municipality, School


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        MUNICIPAL_MANAGER = "MUNICIPAL_MANAGER", "Gestor municipal"
        SCHOOL_MANAGER = "SCHOOL_MANAGER", "Gestor escolar"
        APPLICATOR = "APPLICATOR", "Aplicador"
        TEACHER = "TEACHER", "Professor"

    role = models.CharField(
        "perfil",
        max_length=30,
        choices=Role.choices,
        default=Role.APPLICATOR,
    )
    municipality = models.ForeignKey(
        Municipality,
        verbose_name="município",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    schools = models.ManyToManyField(
        School,
        verbose_name="escolas",
        related_name="users",
        blank=True,
    )
    phone = models.CharField(
        "telefone",
        max_length=20,
        blank=True,
    )
    is_active = models.BooleanField(
        "ativo",
        default=True,
    )

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["first_name", "username"]

    def __str__(self):
        full_name = self.get_full_name()

        if full_name:
            return full_name

        return self.username