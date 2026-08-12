from django.contrib import admin

from .forms import AssessmentAdminForm
from .models import Assessment, AssessmentVersion, Question

class AssessmentVersionInline(admin.TabularInline):
    model = AssessmentVersion
    extra = 0
    fields = (
        "code",
        "question_count",
        "option_count",
        "total_score",
        "is_active",
    )
    show_change_link = True


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    form = AssessmentAdminForm

    list_display = (
        "title",
        "code",
        "subject",
        "academic_year",
        "status",
        "get_version_count",
        "updated_at",
    )
    list_filter = (
        "status",
        "academic_year",
        "subject",
        "grades",
    )
    search_fields = (
        "title",
        "code",
        "description",
    )
    autocomplete_fields = (
        "academic_year",
        "subject",
    )
    filter_horizontal = (
        "grades",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    inlines = (
        AssessmentVersionInline,
    )

    fieldsets = (
        (
            "Identificação",
            {
                "fields": (
                    "title",
                    "code",
                    "description",
                    "academic_year",
                    "subject",
                    "grades",
                )
            },
        ),
        (
            "Materiais",
            {
                "fields": (
                    "instructions",
                    "source_file",
                )
            },
        ),
        (
            "Publicação",
            {
                "fields": (
                    "status",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Versões")
    def get_version_count(self, obj):
        return obj.version_count


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = (
        "number",
        "correct_answer",
        "weight",
        "descriptor_code",
        "descriptor",
        "is_active",
    )
    ordering = (
        "number",
    )


@admin.register(AssessmentVersion)
class AssessmentVersionAdmin(admin.ModelAdmin):
    list_display = (
        "assessment",
        "code",
        "question_count",
        "registered_questions",
        "answer_key_status",
        "total_score",
        "is_active",
    )
    list_filter = (
        "is_active",
        "assessment__status",
        "assessment__academic_year",
        "assessment__subject",
    )
    search_fields = (
        "assessment__title",
        "assessment__code",
        "code",
    )
    autocomplete_fields = (
        "assessment",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    inlines = (
        QuestionInline,
    )

    @admin.display(description="Cadastradas")
    def registered_questions(self, obj):
        return obj.registered_question_count

    @admin.display(
        description="Gabarito",
        boolean=True,
    )
    def answer_key_status(self, obj):
        return obj.is_answer_key_complete


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "version",
        "number",
        "correct_answer",
        "weight",
        "descriptor_code",
        "is_active",
    )
    list_filter = (
        "version__assessment",
        "version",
        "correct_answer",
        "is_active",
    )
    search_fields = (
        "version__assessment__title",
        "version__assessment__code",
        "statement",
        "descriptor_code",
        "descriptor",
    )
    autocomplete_fields = (
        "version",
    )
    ordering = (
        "version",
        "number",
    )

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)