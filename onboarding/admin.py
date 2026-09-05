from django.contrib import admin

from .models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    prepopulated_fields = {"code": ("name",)}


@admin.register(ProgrammeVersion)
class ProgrammeVersionAdmin(admin.ModelAdmin):
    list_display = ("programme", "version", "status", "published_at")
    list_filter = ("status",)


@admin.register(Enrolment)
class EnrolmentAdmin(admin.ModelAdmin):
    list_display = ("student", "programme_version", "status", "enrolled_at")
    list_filter = ("status", "programme_version")
    autocomplete_fields = ("student",)


@admin.register(DisclaimerVersion)
class DisclaimerVersionAdmin(admin.ModelAdmin):
    list_display = ("version", "title", "is_current", "published_at")
    list_filter = ("is_current",)


@admin.register(DisclaimerAcceptance)
class DisclaimerAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("user", "disclaimer", "accepted_at")
    readonly_fields = ("user", "disclaimer", "accepted_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
