from django.contrib import admin

from .models import SimulationRequest


@admin.register(SimulationRequest)
class SimulationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "protocol",
        "requester_institution",
        "municipality_display",
        "preferred_date",
        "estimated_student_count",
        "status",
        "assigned_to",
        "created_at",
    )
    list_filter = (
        "status",
        "state",
        "request_scope",
        "objective",
        "assessment_source",
        "preferred_date",
        "created_at",
    )
    search_fields = (
        "protocol",
        "requester_name",
        "requester_email",
        "requester_institution",
        "municipality_name",
        "school_name",
        "school_inep_code",
    )
    autocomplete_fields = (
        "assigned_to",
    )
    filter_horizontal = (
        "grades",
        "subjects",
    )
    readonly_fields = (
        "protocol",
        "privacy_accepted",
        "privacy_accepted_at",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    ordering = (
        "-created_at",
    )
    list_per_page = 30
    save_on_top = True

    fieldsets = (
        (
            "Controle",
            {
                "fields": (
                    "protocol",
                    "status",
                    "assigned_to",
                    "internal_notes",
                )
            },
        ),
        (
            "Solicitante",
            {
                "fields": (
                    "requester_name",
                    "requester_role",
                    "requester_email",
                    "requester_phone",
                    "requester_institution",
                )
            },
        ),
        (
            "Instituição",
            {
                "fields": (
                    "state",
                    "municipality_name",
                    "request_scope",
                    "education_department_name",
                    "school_name",
                    "school_inep_code",
                )
            },
        ),
        (
            "Planejamento",
            {
                "fields": (
                    "preferred_date",
                    "alternative_date",
                    "academic_year",
                    "grades",
                    "subjects",
                    "estimated_school_count",
                    "estimated_classroom_count",
                    "estimated_student_count",
                    "estimated_question_count",
                    "objective",
                    "objective_details",
                )
            },
        ),
        (
            "Operação",
            {
                "fields": (
                    "assessment_source",
                    "print_responsibility",
                    "applicator_responsibility",
                    "has_scanning_devices",
                    "internet_quality",
                    "notes",
                )
            },
        ),
        (
            "Privacidade e histórico",
            {
                "fields": (
                    "privacy_accepted",
                    "privacy_accepted_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    actions = (
        "mark_under_review",
        "mark_approved",
        "mark_waiting_information",
    )

    @admin.display(description="Município")
    def municipality_display(self, obj):
        return f"{obj.municipality_name}/{obj.state}"

    @admin.action(description="Marcar como em análise")
    def mark_under_review(self, request, queryset):
        updated = queryset.update(
            status=SimulationRequest.Status.UNDER_REVIEW,
        )

        self.message_user(
            request,
            f"{updated} solicitação(ões) marcada(s) como em análise.",
        )

    @admin.action(description="Marcar como aprovada")
    def mark_approved(self, request, queryset):
        updated = queryset.update(
            status=SimulationRequest.Status.APPROVED,
        )

        self.message_user(
            request,
            f"{updated} solicitação(ões) aprovada(s).",
        )

    @admin.action(
        description="Marcar como aguardando informações",
    )
    def mark_waiting_information(self, request, queryset):
        updated = queryset.update(
            status=(
                SimulationRequest.Status.WAITING_INFORMATION
            ),
        )

        self.message_user(
            request,
            (
                f"{updated} solicitação(ões) marcada(s) como "
                "aguardando informações."
            ),
        )