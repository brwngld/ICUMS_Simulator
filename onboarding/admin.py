from django.contrib import admin
from django.contrib.auth.models import Group

from audit.models import AuditEvent
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
    list_display = ("student", "programme_version", "status", "enrolled_at", "enrolled_by")
    list_filter = ("status", "programme_version")
    autocomplete_fields = ("student",)
    readonly_fields = ("enrolled_at", "enrolled_by")

    def save_model(self, request, obj, form, change):
        previous_status = Enrolment.objects.only("status").get(pk=obj.pk).status if change else None
        if not change:
            obj.enrolled_by = request.user
        super().save_model(request, obj, form, change)
        obj.student.groups.add(Group.objects.get(name="Student"))
        if not change or previous_status != obj.status:
            AuditEvent.objects.create(
                actor=request.user,
                action_code="enrolment.created" if not change else "enrolment.status_changed",
                target_type="enrolment",
                target_id=str(obj.pk),
                summary=f"{obj.student} enrolled in {obj.programme_version}." if not change else f"Enrolment status changed from {previous_status} to {obj.status}.",
            )

    def has_delete_permission(self, request, obj=None):
        return False


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
