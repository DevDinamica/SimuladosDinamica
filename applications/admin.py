from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django import forms

from .models import (
    AnswerEntry,
    AnswerSheet,
    AnswerSheetBreakdown,
    ApplicationClassroom,
    Participation,
    SimulationApplication,
    AnswerSheetImageSubmission,
    CardSubmissionPortal,
    ApplicationAssessment,
    ParticipationCard,
)

from .services import (ensure_primary_application_assessment, generate_application_participations,)
from data_portal.models import DataPreparationPortal

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .correction import (
    initialize_answer_sheet,
    process_answer_sheet,
    refresh_participation_status,
    reopen_answer_sheet,
    validate_answer_sheet,
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


class ApplicationAssessmentInline(
    admin.TabularInline
):
    model = ApplicationAssessment
    extra = 0
    fields = (
        "assessment",
        "order",
        "is_active",
    )
    autocomplete_fields = (
        "assessment",
    )
    ordering = (
        "order",
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
        ApplicationAssessmentInline,
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
                "participation_card",
                (
                    "participation_card__"
                    "assessment_version"
                ),
                (
                    "participation_card__"
                    "application_assessment__"
                    "assessment"
                ),
                (
                    "participation_card__"
                    "application_assessment__"
                    "assessment__subject"
                ),
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

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        super().save_model(
            request,
            obj,
            form,
            change,
        )

        ensure_primary_application_assessment(
            obj
        )

@admin.register(ApplicationAssessment)
class ApplicationAssessmentAdmin(
    admin.ModelAdmin
):
    list_display = (
        "application",
        "assessment",
        "subject_display",
        "order",
        "is_active",
    )
    list_filter = (
        "is_active",
        "assessment__subject",
        "assessment__academic_year",
    )
    search_fields = (
        "application__code",
        "application__title",
        "assessment__code",
        "assessment__title",
    )
    autocomplete_fields = (
        "application",
        "assessment",
    )

    @admin.display(description="Disciplina")
    def subject_display(self, obj):
        return obj.subject_name


@admin.register(ParticipationCard)
class ParticipationCardAdmin(
    admin.ModelAdmin
):
    list_display = (
        "sequence_number",
        "student_display",
        "application_display",
        "subject_display",
        "assessment_version",
        "short_code_display",
        "status",
    )
    list_filter = (
        "status",
        "application_assessment__application",
        (
            "application_assessment__"
            "assessment__subject"
        ),
        "assessment_version",
    )
    search_fields = (
        "participation__student__full_name",
        (
            "participation__student__"
            "registration_code"
        ),
        (
            "application_assessment__"
            "application__code"
        ),
        "card_code",
    )
    autocomplete_fields = (
        "participation",
        "application_assessment",
        "assessment_version",
    )
    readonly_fields = (
        "card_code",
        "short_code_display",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Aluno")
    def student_display(self, obj):
        return obj.participation.student

    @admin.display(description="Aplicação")
    def application_display(self, obj):
        return (
            obj.application_assessment
            .application
        )

    @admin.display(description="Disciplina")
    def subject_display(self, obj):
        return obj.subject_name

    @admin.display(description="Código curto")
    def short_code_display(self, obj):
        return obj.short_card_code

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
        "subject_display",
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
        (
            "participation_card__"
            "application_assessment__application"
        ),
        (
            "participation__application_classroom__"
            "classroom__school"
        ),
        (
            "participation_card__"
            "application_assessment__assessment__subject"
        ),
        "participation_card__assessment_version",
    )
    search_fields = (
        "participation__student__full_name",
        "participation__student__registration_code",
        (
            "participation_card__"
            "application_assessment__application__code"
        ),
        "participation_card__card_code",
    )
    readonly_fields = (
        "participation",
        "participation_card",
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
                    "participation_card",
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
        "participation_card",
        (
            "participation_card__"
            "application_assessment"
        ),
        (
            "participation_card__"
            "application_assessment__application"
        ),
        (
            "participation_card__"
            "application_assessment__assessment"
        ),
        (
            "participation_card__"
            "application_assessment__assessment__subject"
        ),
        "participation_card__assessment_version",
    )
    save_on_top = True

    def has_add_permission(self, request):
        return False

    @admin.display(description="Nº")
    def sequence_display(self, obj):
        return obj.participation_card.sequence_number
    
    @admin.display(description="Disciplina")
    def subject_display(self, obj):
        return obj.participation_card.subject_name

    @admin.display(description="Aluno")
    def student_display(self, obj):
        return obj.participation.student.full_name

    @admin.display(description="Aplicação")
    def application_display(self, obj):
        return obj.participation.application.code

    @admin.display(description="Versão")
    def version_display(self, obj):
        return (
            obj.participation_card
            .assessment_version
            .code
        )

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
        card = obj.participation_card
        version = card.assessment_version

        return (
            f"{card.subject_name} — "
            f"Versão {version.code} — "
            f"{version.question_count} questões — "
            f"Código {card.short_card_code}"
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

        participation_card = (
            answer_sheet.participation_card
        )

        if (
            participation_card.status
            != ParticipationCard.Status.RECEIVED
        ):
            participation_card.status = (
                ParticipationCard.Status.RECEIVED
            )
            participation_card.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        refresh_participation_status(
            answer_sheet.participation
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
        "answer_sheets_display",
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

    @admin.display(description="Lançamentos")
    def answer_sheets_display(self, obj):
        cards = obj.discipline_cards.exclude(
            status=ParticipationCard.Status.CANCELLED,
        )

        total = cards.count()
        initialized = cards.filter(
            answer_sheet__isnull=False,
        ).count()
        processed = cards.filter(
            status=ParticipationCard.Status.PROCESSED,
        ).count()

        return (
            f"{initialized}/{total} iniciados — "
            f"{processed}/{total} processados"
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
        ).prefetch_related(
            "discipline_cards",
            (
                "discipline_cards__"
                "application_assessment"
            ),
            (
                "discipline_cards__"
                "application_assessment__assessment"
            ),
            (
                "discipline_cards__"
                "assessment_version"
            ),
        )

        for participation in queryset:
            cards = (
                participation.discipline_cards
                .exclude(
                    status=(
                        ParticipationCard.Status.CANCELLED
                    ),
                )
                .filter(
                    application_assessment__is_active=True,
                )
                .order_by(
                    "application_assessment__order",
                    "pk",
                )
            )

            for participation_card in cards:
                try:
                    _, created = initialize_answer_sheet(
                        participation_card,
                        user=request.user,
                    )

                    if created:
                        created_count += 1
                    else:
                        existing_count += 1

                except ValidationError as error:
                    failures.append(
                        (
                            f"{participation_card}: "
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

@admin.register(CardSubmissionPortal)
class CardSubmissionPortalAdmin(
    admin.ModelAdmin
):
    list_display = (
        "application",
        "contact_name",
        "portal_status",
        "expires_at",
        "submission_count_display",
        "portal_link",
    )
    list_filter = (
        "is_active",
        "expires_at",
        "application__status",
    )
    search_fields = (
        "application__code",
        "application__title",
        "contact_name",
        "contact_email",
    )
    readonly_fields = (
        "token",
        "portal_link",
        "submission_count_display",
        "created_at",
        "updated_at",
    )
    list_select_related = (
        "application",
    )
    actions = (
        "activate_selected",
        "deactivate_selected",
        "extend_selected",
    )

    fieldsets = (
        (
            "Aplicação",
            {
                "fields": (
                    "application",
                    "contact_name",
                    "contact_email",
                ),
            },
        ),
        (
            "Acesso",
            {
                "fields": (
                    "token",
                    "portal_link",
                    "expires_at",
                    "is_active",
                ),
            },
        ),
        (
            "Orientações",
            {
                "fields": (
                    "instructions",
                ),
            },
        ),
        (
            "Controle",
            {
                "fields": (
                    "submission_count_display",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(
        description="Situação",
        boolean=True,
    )
    def portal_status(self, obj):
        return obj.can_be_accessed

    @admin.display(
        description="Envios",
    )
    def submission_count_display(
        self,
        obj,
    ):
        return obj.submission_count

    @admin.display(
        description="Link do portal",
    )
    def portal_link(self, obj):
        if not obj.pk:
            return "Salve para gerar o link."

        path = (
            f"/cartoes/{obj.token}/"
        )

        return format_html(
            (
                '<a href="{}" target="_blank">'
                "Abrir portal de envio"
                "</a>"
            ),
            path,
        )

    @admin.action(
        description=(
            "Ativar portais selecionados"
        ),
    )
    def activate_selected(
        self,
        request,
        queryset,
    ):
        count = queryset.update(
            is_active=True,
        )

        self.message_user(
            request,
            f"{count} portal(is) ativado(s).",
        )

    @admin.action(
        description=(
            "Desativar portais selecionados"
        ),
    )
    def deactivate_selected(
        self,
        request,
        queryset,
    ):
        count = queryset.update(
            is_active=False,
        )

        self.message_user(
            request,
            f"{count} portal(is) desativado(s).",
        )

    @admin.action(
        description=(
            "Prorrogar validade por 30 dias"
        ),
    )
    def extend_selected(
        self,
        request,
        queryset,
    ):
        count = 0

        for portal in queryset:
            portal.expires_at = (
                timezone.now()
                + timedelta(days=30)
            )
            portal.is_active = True
            portal.save(
                update_fields=[
                    "expires_at",
                    "is_active",
                    "updated_at",
                ]
            )
            count += 1

        self.message_user(
            request,
            (
                f"A validade de {count} "
                "portal(is) foi prorrogada."
            ),
        )

@admin.register(
    AnswerSheetImageSubmission
)
class AnswerSheetImageSubmissionAdmin(
    admin.ModelAdmin
):
    list_display = (
        "protocol_display",
        "student_display",
        "subject_display",
        "version_display",
        "school_display",
        "classroom_display",
        "application_display",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "portal__application",
        (
            "participation__"
            "application_classroom__"
            "classroom__school"
        ),
        (
            "participation__"
            "application_classroom__"
            "classroom__grade"
        ),
        (
            "participation_card__"
            "application_assessment__"
            "assessment__subject"
        ),
        (
            "participation_card__"
            "assessment_version"
        ),
        "created_at",
    )
    search_fields = (
        "submission_code",
        "participation__student__full_name",
        (
            "participation__student__"
            "registration_code"
        ),
        "participation__card_code",
        "portal__application__code",
        (
            "participation__"
            "application_classroom__"
            "classroom__school__name"
        ),
        "participation_card__card_code",
        (
            "participation_card__"
            "application_assessment__"
            "assessment__title"
        ),
    )
    readonly_fields = (
        "submission_code",
        "protocol_display",
        "secure_image_preview",
        "original_name",
        "file_size_display",
        "created_at",
        "updated_at",
    )
    list_select_related = (
        "portal",
        "portal__application",
        "participation",
        "participation__student",
        (
            "participation__"
            "application_classroom__"
            "classroom"
        ),
        (
            "participation__"
            "application_classroom__"
            "classroom__school"
        ),
    )
    actions = (
        "mark_under_review",
        "mark_accepted",
        "mark_rejected",
    )

    fieldsets = (
        (
            "Envio",
            {
                "fields": (
                    "portal",
                    "participation",
                    "submission_code",
                    "protocol_display",
                    "secure_image_preview",
                    "original_name",
                    "file_size_display",
                    "sender_name",
                ),
            },
        ),
        (
            "Revisão",
            {
                "fields": (
                    "status",
                    "review_notes",
                ),
            },
        ),
        (
            "Controle",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )
    
    @admin.display(
        description="Imagem do cartão-resposta",
    )
    def secure_image_preview(
        self,
        obj,
    ):
        if not obj.pk or not obj.image:
            return "Nenhuma imagem enviada."

        url = reverse(
            "card_submission:secure_image",
            kwargs={
                "submission_code": (
                    obj.submission_code
                ),
            },
        )

        return format_html(
            (
                '<a href="{}" target="_blank">'
                '<img src="{}" alt="Cartão-resposta" '
                'style="max-width: 420px; '
                'max-height: 560px; '
                'border-radius: 8px; '
                'object-fit: contain;">'
                "</a>"
            ),
            url,
            url,
        )

    @admin.display(
        description="Protocolo",
    )
    def protocol_display(
        self,
        obj,
    ):
        return obj.protocol

    @admin.display(
        description="Aluno",
        ordering=(
            "participation__"
            "student__full_name"
        ),
    )
    def student_display(
        self,
        obj,
    ):
        return (
            obj.participation
            .student
            .full_name
        )

    @admin.display(
        description="Escola",
        ordering=(
            "participation__"
            "application_classroom__"
            "classroom__school__name"
        ),
    )
    def school_display(
        self,
        obj,
    ):
        return (
            obj.participation
            .application_classroom
            .classroom
            .school
            .name
        )

    @admin.display(
        description="Turma",
    )
    def classroom_display(
        self,
        obj,
    ):
        classroom = (
            obj.participation
            .application_classroom
            .classroom
        )

        return (
            f"{classroom.grade.name} "
            f"{classroom.name}"
        )

    @admin.display(
        description="Aplicação",
        ordering=(
            "portal__application__code"
        ),
    )
    def application_display(
        self,
        obj,
    ):
        return (
            obj.portal.application.code
        )
        
    @admin.display(
        description="Disciplina",
        ordering=(
            "participation_card__"
            "application_assessment__"
            "assessment__subject__name"
        ),
    )
    def subject_display(self, obj):
        if not obj.participation_card_id:
            return "Envio legado"

        return (
            obj.participation_card
            .subject_name
        )

    @admin.display(
        description="Versão",
        ordering=(
            "participation_card__"
            "assessment_version__code"
        ),
    )
    def version_display(self, obj):
        if not obj.participation_card_id:
            return "-"

        return (
            obj.participation_card
            .assessment_version
            .code
        )

    @admin.display(
        description="Tamanho",
    )
    def file_size_display(
        self,
        obj,
    ):
        if not obj.file_size:
            return "—"

        megabytes = (
            obj.file_size
            / 1024
            / 1024
        )

        return f"{megabytes:.2f} MB"

    @admin.action(
        description="Marcar como em revisão",
    )
    def mark_under_review(
        self,
        request,
        queryset,
    ):
        count = queryset.update(
            status=(
                AnswerSheetImageSubmission
                .Status
                .UNDER_REVIEW
            )
        )

        self.message_user(
            request,
            f"{count} cartão(ões) em revisão.",
        )

    @admin.action(
        description="Marcar como aceito",
    )
    def mark_accepted(
        self,
        request,
        queryset,
    ):
        count = queryset.update(
            status=(
                AnswerSheetImageSubmission
                .Status
                .ACCEPTED
            )
        )

        self.message_user(
            request,
            f"{count} cartão(ões) aceito(s).",
        )

    @admin.action(
        description="Marcar como rejeitado",
    )
    def mark_rejected(
        self,
        request,
        queryset,
    ):
        count = queryset.update(
            status=(
                AnswerSheetImageSubmission
                .Status
                .REJECTED
            )
        )

        self.message_user(
            request,
            f"{count} cartão(ões) rejeitado(s).",
        )
    def __str__(self):
        subject = (
            self.participation_card.subject_name
            if self.participation_card_id
            else "Envio legado"
        )

        return (
            f"{self.protocol} — "
            f"{self.participation.student.full_name} — "
            f"{subject}"
        )