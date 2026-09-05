from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class SimulatorUserAdmin(UserAdmin):
    readonly_fields = ("created_at", "updated_at")
    fieldsets = UserAdmin.fieldsets + (
        ("Simulator record", {"fields": ("created_at", "updated_at")}),
    )
