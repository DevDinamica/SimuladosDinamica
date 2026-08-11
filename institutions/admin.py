from django.contrib import admin

from .models import Municipality, School


@admin.register(Municipality)
class MunicipalityAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "state",
        "ibge_code",
        "is_active",
    )
    list_filter = (
        "state",
        "is_active",
    )
    search_fields = (
        "name",
        "ibge_code",
    )
    ordering = (
        "name",
    )


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "municipality",
        "inep_code",
        "is_active",
    )
    list_filter = (
        "municipality",
        "is_active",
    )
    search_fields = (
        "name",
        "inep_code",
        "municipality__name",
    )
    autocomplete_fields = (
        "municipality",
    )
    ordering = (
        "municipality__name",
        "name",
    )