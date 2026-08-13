from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django import forms

from .models import (
    ApplicationClassroom,
    Participation,
    SimulationApplication,
)
from .services import generate_application_participations

class ApplicationClassroomInlineFormSet(
    forms.models.BaseInlineFormSet
):
    def clean(self):
        super().clean()

        application = self.instance

        if not application.assessment_id:
            return

        allowed_grade_ids = set(
            application.assessment.grades.values_list(
                "id",
                flat=True,
            )
        )

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            classroom = form.cleaned_data.get("classroom")

            if not classroom:
                continue

            if (
                classroom.school.municipality_id
                != application.municipality_id
            ):
                form.add_error(
                    "classroom",
                    (
                        "A turma precisa pertencer ao município "
                        "da aplicação."
                    ),
                )

            if classroom.grade_id not in allowed_grade_ids:
                form.add_error(
                    "classroom",
                    (
                        "A série desta turma não está contemplada "
                        "pela prova selecionada."
                    ),
                )

            if (
                classroom.academic_year_id
                != application.assessment.academic_year_id
            ):
                form.add_error(
                    "classroom",
                    (
                        "O ano letivo da turma deve ser o mesmo "
                        "da prova."
                    ),
                )


class ApplicationClassroomInline(admin.TabularInline):
    model = ApplicationClassroom
    formset = ApplicationClassroomInlineFormSet
    extra = 0
    fields = (
        "classroom",
        "room_name",
        "is_active",
    )
    autocomplete_fields = (
        "classroom",
    )
    show_change_link = True


@admin.register(SimulationApplication)
class SimulationApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "assessment",
        "municipality",
        "application_date",
        "status",
        "classroom_total",
        "participant_total",
    )
    list_filter = (
        "status",
        "municipality",
        "application_date",
        "assessment__subject",
        "assessment__academic_year",
    )
    search_fields = (
        "code",
        "title",
        "assessment__title",
        "assessment__code",
        "municipality__name",
        "simulation_request__protocol",
    )
    autocomplete_fields = (
        "simulation_request",
        "assessment",
        "municipality",
        "coordinator",
    )
    readonly_fields = (
        "code",
        "created_at",
        "updated_at",
        "classroom_count_display",
        "participant_count_display",
    )
    inlines = (
        ApplicationClassroomInline,
    )
    date_hierarchy = "application_date"
    save_on_top = True
    actions = (
        "generate_participations",
        "mark_as_preparing",
        "mark_as_ready",
    )

    fieldsets = (
        (
            "Identificação",
            {
                "fields": (
                    "code",
                    "title",
                    "simulation_request",
                    "assessment",
                    "municipality",
                    "coordinator",
                )
            },
        ),
        (
            "Agendamento",
            {
                "fields": (
                    "application_date",
                    "alternative_date",
                    "start_time",
                    "end_time",
                    "status",
                )
            },
        ),
        (
            "Operação",
            {
                "fields": (
                    "general_instructions",
                    "internal_notes",
                    "classroom_count_display",
                    "participant_count_display",
                )
            },
        ),
        (
            "Histórico",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "assessment",
                "municipality",
            )
            .annotate(
                classroom_total_annotation=Count(
                    "application_classrooms",
                    distinct=True,
                ),
                participant_total_annotation=Count(
                    "participations",
                    distinct=True,
                ),
            )
        )

    @admin.display(description="Turmas")
    def classroom_total(self, obj):
        return obj.classroom_total_annotation

    @admin.display(description="Participantes")
    def participant_total(self, obj):
        return obj.participant_total_annotation

    @admin.display(description="Turmas vinculadas")
    def classroom_count_display(self, obj):
        if not obj.pk:
            return 0

        return obj.classroom_count

    @admin.display(description="Participações geradas")
    def participant_count_display(self, obj):
        if not obj.pk:
            return 0

        return obj.participant_count

    @admin.action(description="Gerar participações dos alunos")
    def generate_participations(self, request, queryset):
        total_created = 0
        total_existing = 0
        failures = []

        for application in queryset:
            try:
                created, existing = (
                    generate_application_participations(
                        application
                    )
                )
                total_created += created
                total_existing += existing
            except ValidationError as error:
                failures.append(
                    f"{application.code}: {'; '.join(error.messages)}"
                )

        if total_created or total_existing:
            self.message_user(
                request,
                (
                    f"{total_created} participação(ões) criada(s); "
                    f"{total_existing} já existia(m)."
                ),
                level=messages.SUCCESS,
            )

        for failure in failures:
            self.message_user(
                request,
                failure,
                level=messages.ERROR,
            )

    @admin.action(description="Marcar como em preparação")
    def mark_as_preparing(self, request, queryset):
        updated = queryset.update(
            status=SimulationApplication.Status.PREPARING,
        )

        self.message_user(
            request,
            f"{updated} aplicação(ões) atualizada(s).",
        )

    @admin.action(description="Marcar como pronta")
    def mark_as_ready(self, request, queryset):
        invalid_applications = queryset.filter(
            participations__isnull=True,
        ).distinct()

        if invalid_applications.exists():
            codes = ", ".join(
                invalid_applications.values_list(
                    "code",
                    flat=True,
                )
            )

            self.message_user(
                request,
                (
                    "As aplicações seguintes não possuem participantes: "
                    f"{codes}."
                ),
                level=messages.ERROR,
            )
            return

        updated = queryset.update(
            status=SimulationApplication.Status.READY,
        )

        self.message_user(
            request,
            f"{updated} aplicação(ões) marcada(s) como pronta(s).",
        )


@admin.register(ApplicationClassroom)
class ApplicationClassroomAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "classroom",
        "school_display",
        "applicator_count",
        "room_name",
        "is_active",
    )
    list_filter = (
        "application",
        "classroom__school__municipality",
        "classroom__school",
        "classroom__grade",
        "is_active",
    )
    search_fields = (
        "application__code",
        "application__title",
        "classroom__school__name",
        "classroom__name",
    )
    autocomplete_fields = (
        "application",
        "classroom",
        "applicators",
    )
    filter_horizontal = (
        "applicators",
    )

    @admin.display(description="Escola")
    def school_display(self, obj):
        return obj.classroom.school

    @admin.display(description="Aplicadores")
    def applicator_count(self, obj):
        return obj.applicators.count()


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = (
        "sequence_number",
        "student",
        "application",
        "classroom_display",
        "assessment_version",
        "short_code_display",
        "status",
    )
    list_filter = (
        "status",
        "application",
        "application_classroom__classroom__school",
        "application_classroom__classroom__grade",
        "assessment_version",
    )
    search_fields = (
        "student__full_name",
        "student__registration_code",
        "application__code",
        "card_code",
    )
    autocomplete_fields = (
        "application",
        "application_classroom",
        "student",
        "enrollment",
        "assessment_version",
    )
    readonly_fields = (
        "card_code",
        "short_code_display",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    actions = (
        "mark_present",
        "mark_absent",
    )

    @admin.display(description="Turma")
    def classroom_display(self, obj):
        return obj.application_classroom.classroom

    @admin.display(description="Código curto")
    def short_code_display(self, obj):
        return obj.short_card_code

    @admin.action(description="Marcar como presente")
    def mark_present(self, request, queryset):
        updated = queryset.update(
            status=Participation.Status.PRESENT,
        )

        self.message_user(
            request,
            f"{updated} aluno(s) marcado(s) como presente(s).",
        )

    @admin.action(description="Marcar como ausente")
    def mark_absent(self, request, queryset):
        updated = queryset.update(
            status=Participation.Status.ABSENT,
        )

        self.message_user(
            request,
            f"{updated} aluno(s) marcado(s) como ausente(s).",
        )