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
from data_portal.models import DataPreparationPortal

from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .correction import (
    initialize_answer_sheet,
    process_answer_sheet,
    reopen_answer_sheet,
    validate_answer_sheet,
)

from .models import (
    AnswerEntry,
    AnswerSheet,
    AnswerSheetBreakdown,
    ApplicationClassroom,
    Participation,
    SimulationApplication,
)

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
    actions = (
        "create_data_portal",
        "generate_participations",
        "mark_as_preparing",
        "mark_as_ready",
    )
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
        "assessment__components__subject",
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
        "create_data_portal",
        "generate_participations",
        "export_answer_sheets",
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

    @admin.action(description="Criar portal de preparação dos dados")
    def create_data_portal(self, request, queryset):
        created_count = 0
        existing_count = 0

        for application in queryset:
            simulation_request = (
                application.simulation_request
            )

            if simulation_request:
                contact_name = (
                    simulation_request.requester_name
                )
                contact_email = (
                    simulation_request.requester_email
                )
            else:
                contact_name = "Responsável institucional"
                contact_email = "responsavel@exemplo.com"

            _, created = (
                DataPreparationPortal.objects.get_or_create(
                    application=application,
                    defaults={
                        "contact_name": contact_name,
                        "contact_email": contact_email,
                    },
                )
            )

            if created:
                created_count += 1
            else:
                existing_count += 1

        self.message_user(
            request,
            (
                f"{created_count} portal(is) criado(s); "
                f"{existing_count} já existia(m)."
            ),
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


class AnswerEntryInline(admin.TabularInline):
    model = AnswerEntry
    extra = 0
    can_delete = False
    fields = (
        "question_number",
        "descriptor_display",
        "marking_status",
        "selected_answer",
        "correct_display",
        "awarded_score",
    )
    readonly_fields = (
        "question_number",
        "descriptor_display",
        "correct_display",
        "awarded_score",
    )
    ordering = (
        "question__number",
    )

    @admin.display(description="Questão")
    def question_number(self, obj):
        if not obj.pk:
            return "—"

        return obj.question.number

    @admin.display(description="Descritor")
    def descriptor_display(self, obj):
        if not obj.pk:
            return "—"

        if obj.question.descriptor_code:
            return (
                f"{obj.question.descriptor_code} — "
                f"{obj.question.descriptor}"
            )

        return "Sem descritor"

    @admin.display(description="Resultado")
    def correct_display(self, obj):
        if not obj.pk or obj.is_correct is None:
            return "Aguardando correção"

        if obj.is_correct:
            return "Correta"

        return "Incorreta"

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        if (
            obj
            and obj.status == AnswerSheet.Status.PROCESSED
        ):
            return False

        return super().has_change_permission(
            request,
            obj,
        )


class AnswerSheetBreakdownInline(admin.TabularInline):
    model = AnswerSheetBreakdown
    extra = 0
    can_delete = False
    fields = (
        "dimension",
        "key",
        "label",
        "question_count",
        "correct_count",
        "incorrect_count",
        "blank_count",
        "multiple_count",
        "score",
        "maximum_score",
        "percentage",
    )
    readonly_fields = fields
    ordering = (
        "dimension",
        "key",
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(AnswerSheet)
class AnswerSheetAdmin(admin.ModelAdmin):
    list_display = (
        "sequence_display",
        "student_display",
        "application_display",
        "version_display",
        "status",
        "correct_count",
        "incorrect_count",
        "blank_count",
        "multiple_count",
        "score",
        "percentage_display",
    )
    list_filter = (
        "status",
        "input_method",
        "participation__application",
        (
            "participation__application_classroom__"
            "classroom__school"
        ),
        "participation__assessment_version",
    )
    search_fields = (
        "participation__student__full_name",
        "participation__student__registration_code",
        "participation__application__code",
        "participation__card_code",
    )
    readonly_fields = (
        "participation",
        "status",
        "input_method",
        "student_summary",
        "application_summary",
        "version_summary",
        "question_count",
        "answered_count",
        "blank_count",
        "multiple_count",
        "correct_count",
        "incorrect_count",
        "score",
        "percentage",
        "entered_by",
        "entered_at",
        "validated_by",
        "validated_at",
        "processed_by",
        "processed_at",
        "processing_message",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Identificação",
            {
                "fields": (
                    "participation",
                    "student_summary",
                    "application_summary",
                    "version_summary",
                    "status",
                    "input_method",
                )
            },
        ),
        (
            "Resultado geral",
            {
                "fields": (
                    "question_count",
                    "answered_count",
                    "correct_count",
                    "incorrect_count",
                    "blank_count",
                    "multiple_count",
                    "score",
                    "percentage",
                    "processing_message",
                )
            },
        ),
        (
            "Operação",
            {
                "fields": (
                    "entered_by",
                    "entered_at",
                    "validated_by",
                    "validated_at",
                    "processed_by",
                    "processed_at",
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
    inlines = (
        AnswerEntryInline,
        AnswerSheetBreakdownInline,
    )
    actions = (
        "validate_selected",
        "process_selected",
        "reopen_selected",
    )
    list_select_related = (
        "participation",
        "participation__student",
        "participation__application",
        "participation__assessment_version",
    )
    save_on_top = True

    def has_add_permission(self, request):
        return False

    @admin.display(description="Nº")
    def sequence_display(self, obj):
        return obj.participation.sequence_number

    @admin.display(description="Aluno")
    def student_display(self, obj):
        return obj.participation.student.full_name

    @admin.display(description="Aplicação")
    def application_display(self, obj):
        return obj.participation.application.code

    @admin.display(description="Versão")
    def version_display(self, obj):
        return obj.participation.assessment_version.code

    @admin.display(description="Percentual")
    def percentage_display(self, obj):
        return f"{obj.percentage:.2f}%"

    @admin.display(description="Aluno")
    def student_summary(self, obj):
        return (
            f"{obj.participation.student.full_name} — "
            f"{obj.participation.student.registration_code}"
        )

    @admin.display(description="Aplicação")
    def application_summary(self, obj):
        return (
            f"{obj.participation.application.code} — "
            f"{obj.participation.application.title}"
        )

    @admin.display(description="Versão da prova")
    def version_summary(self, obj):
        version = obj.participation.assessment_version

        return (
            f"Versão {version.code} — "
            f"{version.question_count} questões"
        )

    def save_formset(
        self,
        request,
        form,
        formset,
        change,
    ):
        has_answer_changes = (
            formset.model is AnswerEntry
            and formset.has_changed()
        )

        instances = formset.save(commit=False)

        for instance in instances:
            instance.save()

        formset.save_m2m()

        if not has_answer_changes:
            return

        answer_sheet = form.instance

        answer_sheet.refresh_from_db(
            fields=[
                "status",
            ]
        )

        if (
            answer_sheet.status
            == AnswerSheet.Status.PROCESSED
        ):
            return

        now = timezone.now()

        AnswerSheet.objects.filter(
            pk=answer_sheet.pk,
        ).update(
            status=AnswerSheet.Status.ENTERED,
            input_method=(
                AnswerSheet.InputMethod.MANUAL
            ),
            entered_by=request.user,
            entered_at=now,
            processing_message=(
                "Respostas digitadas; aguardando validação."
            ),
            updated_at=now,
        )

        Participation.objects.filter(
            pk=answer_sheet.participation_id,
        ).update(
            status=(
                Participation.Status
                .ANSWER_SHEET_RECEIVED
            ),
            updated_at=now,
        )

    @admin.action(
        description="Validar lançamentos selecionados",
    )
    def validate_selected(self, request, queryset):
        successes = 0
        failures = []

        for answer_sheet in queryset:
            try:
                validate_answer_sheet(
                    answer_sheet,
                    user=request.user,
                )
                successes += 1
            except ValidationError as error:
                failures.append(
                    (
                        f"{answer_sheet}: "
                        f"{'; '.join(error.messages)}"
                    )
                )

        if successes:
            self.message_user(
                request,
                f"{successes} cartão(ões) validado(s).",
                level=messages.SUCCESS,
            )

        for failure in failures:
            self.message_user(
                request,
                failure,
                level=messages.ERROR,
            )

    @admin.action(
        description="Processar cartões selecionados",
    )
    def process_selected(self, request, queryset):
        successes = 0
        failures = []

        for answer_sheet in queryset:
            try:
                if (
                    answer_sheet.status
                    != AnswerSheet.Status.VALIDATED
                ):
                    validate_answer_sheet(
                        answer_sheet,
                        user=request.user,
                    )

                process_answer_sheet(
                    answer_sheet,
                    user=request.user,
                )
                successes += 1
            except ValidationError as error:
                failures.append(
                    (
                        f"{answer_sheet}: "
                        f"{'; '.join(error.messages)}"
                    )
                )

        if successes:
            self.message_user(
                request,
                f"{successes} cartão(ões) processado(s).",
                level=messages.SUCCESS,
            )

        for failure in failures:
            self.message_user(
                request,
                failure,
                level=messages.ERROR,
            )

    @admin.action(
        description="Reabrir cartões processados",
    )
    def reopen_selected(self, request, queryset):
        successes = 0
        failures = []

        for answer_sheet in queryset:
            try:
                reopen_answer_sheet(answer_sheet)
                successes += 1
            except ValidationError as error:
                failures.append(
                    (
                        f"{answer_sheet}: "
                        f"{'; '.join(error.messages)}"
                    )
                )

        if successes:
            self.message_user(
                request,
                f"{successes} cartão(ões) reaberto(s).",
                level=messages.SUCCESS,
            )

        for failure in failures:
            self.message_user(
                request,
                failure,
                level=messages.ERROR,
            )


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
        "answer_sheet_display",
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
        "initialize_answer_sheets",
        "export_selected_answer_sheets",
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

    @admin.display(description="Lançamento")
    def answer_sheet_display(self, obj):
        try:
            answer_sheet = obj.answer_sheet
        except AnswerSheet.DoesNotExist:
            return "Não iniciado"

        url = reverse(
            "admin:applications_answersheet_change",
            args=[answer_sheet.pk],
        )

        return format_html(
            '<a href="{}">{}</a>',
            url,
            answer_sheet.get_status_display(),
        )

    @admin.action(
        description="Inicializar lançamento dos cartões",
    )
    def initialize_answer_sheets(
        self,
        request,
        queryset,
    ):
        created_count = 0
        existing_count = 0
        failures = []

        queryset = queryset.select_related(
            "application",
            "student",
            "assessment_version",
        )

        for participation in queryset:
            try:
                _, created = initialize_answer_sheet(
                    participation,
                    user=request.user,
                )

                if created:
                    created_count += 1
                else:
                    existing_count += 1

            except ValidationError as error:
                failures.append(
                    (
                        f"{participation}: "
                        f"{'; '.join(error.messages)}"
                    )
                )

        if created_count or existing_count:
            self.message_user(
                request,
                (
                    f"{created_count} cartão(ões) iniciado(s); "
                    f"{existing_count} já existia(m)."
                ),
                level=messages.SUCCESS,
            )

        for failure in failures:
            self.message_user(
                request,
                failure,
                level=messages.ERROR,
            )