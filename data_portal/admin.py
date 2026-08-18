from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    DataPreparationPortal,
    SpreadsheetUpload,
)
from .services import import_validated_upload


class SpreadsheetUploadInline(admin.TabularInline):
    model = SpreadsheetUpload
    extra = 0
    fields = (
        "original_name",
        "status",
        "school_count",
        "classroom_count",
        "student_count",
        "error_count",
        "created_at",
    )
    readonly_fields = fields
    can_delete = False
    show_change_link = True


@admin.register(DataPreparationPortal)
class DataPreparationPortalAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "contact_name",
        "status",
        "expires_at",
        "is_active",
        "portal_link",
    )
    list_filter = (
        "status",
        "is_active",
        "expires_at",
    )
    search_fields = (
        "application__code",
        "application__title",
        "contact_name",
        "contact_email",
    )
    autocomplete_fields = (
        "application",
    )
    readonly_fields = (
        "token",
        "portal_link",
        "created_at",
        "updated_at",
        "submitted_at",
        "imported_at",
    )
    inlines = (
        SpreadsheetUploadInline,
    )

    @admin.display(description="Link")
    def portal_link(self, obj):
        if not obj.pk:
            return "Salve o portal para gerar o link."

        path = reverse(
            "data_portal:detail",
            kwargs={"token": obj.token},
        )

        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            path,
            path,
        )


@admin.register(SpreadsheetUpload)
class SpreadsheetUploadAdmin(admin.ModelAdmin):
    list_display = (
        "portal",
        "original_name",
        "status",
        "school_count",
        "classroom_count",
        "student_count",
        "error_count",
        "created_at",
    )
    list_filter = (
        "status",
        "created_at",
    )
    search_fields = (
        "portal__application__code",
        "portal__contact_name",
        "original_name",
    )
    readonly_fields = (
        "portal",
        "file",
        "original_name",
        "status",
        "school_count",
        "classroom_count",
        "student_count",
        "error_count",
        "warning_count",
        "validation_report",
        "created_at",
        "imported_at",
    )
    actions = (
        "import_selected_uploads",
    )

    @admin.action(
        description="Importar planilhas validadas",
    )
    def import_selected_uploads(self, request, queryset):
        for upload in queryset:
            try:
                result = import_validated_upload(
                    upload
                )

                self.message_user(
                    request,
                    (
                        f"{upload.original_name}: "
                        f"{result['schools_created']} escolas, "
                        f"{result['classrooms_created']} turmas, "
                        f"{result['students_created']} alunos e "
                        f"{result['enrollments_created']} matrículas "
                        "criados."
                    ),
                    level=messages.SUCCESS,
                )
            except Exception as error:
                self.message_user(
                    request,
                    f"{upload.original_name}: {error}",
                    level=messages.ERROR,
                )