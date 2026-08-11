from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "get_full_name",
        "role",
        "municipality",
        "is_active",
        "is_staff",
    )
    list_filter = (
        "role",
        "municipality",
        "is_active",
        "is_staff",
    )
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "phone",
    )
    autocomplete_fields = (
        "municipality",
        "schools",
    )
    filter_horizontal = (
        "groups",
        "user_permissions",
    )

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Dinâmica Simulados",
            {
                "fields": (
                    "role",
                    "municipality",
                    "schools",
                    "phone",
                )
            },
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Dinâmica Simulados",
            {
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "role",
                    "municipality",
                    "schools",
                    "phone",
                )
            },
        ),
    )