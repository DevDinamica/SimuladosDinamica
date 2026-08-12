from django.contrib import admin

from .models import (
    AcademicYear,
    Classroom,
    EducationStage,
    Enrollment,
    Grade,
    Student,
    Subject,
)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = (
        "year",
        "is_current",
        "is_active",
    )
    list_filter = (
        "is_current",
        "is_active",
    )
    search_fields = (
        "=year",
    )
    ordering = (
        "-year",
    )


@admin.register(EducationStage)
class EducationStageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "order",
        "is_active",
    )
    list_editable = (
        "order",
        "is_active",
    )
    search_fields = (
        "name",
    )
    ordering = (
        "order",
        "name",
    )


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "stage",
        "code",
        "order",
        "is_active",
    )
    list_filter = (
        "stage",
        "is_active",
    )
    list_editable = (
        "order",
        "is_active",
    )
    search_fields = (
        "name",
        "code",
    )
    autocomplete_fields = (
        "stage",
    )


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "is_active",
    )
    list_filter = (
        "is_active",
    )
    search_fields = (
        "name",
        "code",
    )
    search_fields = (
        "name",
        "code",
    )


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    autocomplete_fields = (
        "classroom",
    )


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "registration_code",
        "school",
        "get_municipality",
        "is_active",
    )
    list_filter = (
        "school__municipality",
        "school",
        "is_active",
    )
    search_fields = (
        "full_name",
        "registration_code",
        "school__name",
    )
    autocomplete_fields = (
        "school",
    )
    inlines = (
        EnrollmentInline,
    )

    @admin.display(description="Município")
    def get_municipality(self, obj):
        return obj.school.municipality


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "grade",
        "school",
        "academic_year",
        "shift",
        "student_count",
        "is_active",
    )
    list_filter = (
        "academic_year",
        "school__municipality",
        "school",
        "grade",
        "shift",
        "is_active",
    )
    search_fields = (
        "name",
        "school__name",
        "grade__name",
    )
    autocomplete_fields = (
        "school",
        "grade",
    )
    filter_horizontal = (
        "subjects",
    )

    @admin.display(description="Alunos")
    def student_count(self, obj):
        return obj.enrollments.filter(
            status=Enrollment.Status.ACTIVE,
        ).count()


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "classroom",
        "status",
        "enrollment_date",
    )
    list_filter = (
        "status",
        "classroom__academic_year",
        "classroom__school__municipality",
        "classroom__school",
        "classroom__grade",
    )
    search_fields = (
        "student__full_name",
        "student__registration_code",
        "classroom__name",
    )
    autocomplete_fields = (
        "student",
        "classroom",
    )