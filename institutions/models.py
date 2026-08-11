from django.db import models


class Municipality(models.Model):
    name = models.CharField(
        "nome",
        max_length=150,
    )
    state = models.CharField(
        "estado",
        max_length=2,
        default="CE",
    )
    ibge_code = models.CharField(
        "código IBGE",
        max_length=10,
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
        verbose_name = "município"
        verbose_name_plural = "municípios"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "state"],
                name="unique_municipality_by_state",
            )
        ]

    def __str__(self):
        return f"{self.name}/{self.state}"


class School(models.Model):
    municipality = models.ForeignKey(
        Municipality,
        verbose_name="município",
        on_delete=models.PROTECT,
        related_name="schools",
    )
    name = models.CharField(
        "nome",
        max_length=200,
    )
    inep_code = models.CharField(
        "código INEP",
        max_length=20,
        blank=True,
    )
    address = models.CharField(
        "endereço",
        max_length=255,
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
        verbose_name = "escola"
        verbose_name_plural = "escolas"
        ordering = ["municipality__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["municipality", "name"],
                name="unique_school_by_municipality",
            )
        ]

    def __str__(self):
        return f"{self.name} — {self.municipality}"