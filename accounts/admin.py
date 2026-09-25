from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from audit.models import AuditEvent
from onboarding.models import Enrolment
from .models import SimulatorCredential, User


class EnrolmentInline(admin.TabularInline):
    model = Enrolment
    fk_name = "student"
    fields = ("programme_version", "status", "enrolled_at", "enrolled_by")
    readonly_fields = ("enrolled_at", "enrolled_by")
    extra = 1
    can_delete = False


@admin.register(User)
class SimulatorUserAdmin(UserAdmin):
    readonly_fields = ("student_id", "created_at", "updated_at")
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Personal info", {"fields": ("email", "first_name", "last_name")}),
    )
    fieldsets = UserAdmin.fieldsets + (
        ("Simulator record", {"fields": ("student_id", "created_at", "updated_at")}),
    )
    inlines = (EnrolmentInline,)

    def save_formset(self, request, form, formset, change):
        if formset.model is not Enrolment:
            return super().save_formset(request, form, formset, change)
        instances = formset.save(commit=False)
        student_group = Group.objects.get(name="Student")
        for enrolment in instances:
            created = enrolment._state.adding
            previous_status = None
            if not created:
                previous_status = Enrolment.objects.only("status").get(pk=enrolment.pk).status
            if created:
                enrolment.enrolled_by = request.user
            enrolment.save()
            enrolment.student.groups.add(student_group)
            action_code = "enrolment.created" if created else "enrolment.status_changed"
            if created or previous_status != enrolment.status:
                AuditEvent.objects.create(
                    actor=request.user,
                    action_code=action_code,
                    target_type="enrolment",
                    target_id=str(enrolment.pk),
                    summary=f"{enrolment.student} enrolled in {enrolment.programme_version}." if created else f"Enrolment status changed from {previous_status} to {enrolment.status}.",
                )
        formset.save_m2m()


@admin.register(SimulatorCredential)
class SimulatorCredentialAdmin(admin.ModelAdmin):
    """Credential status only: the password itself is shown once, on the instructor dashboard."""

    list_display = ("user", "student_id", "password_state_display", "issued_at", "expires_at", "is_current", "reset_requested_at")
    search_fields = ("user__username", "user__student_id", "user__first_name", "user__last_name")
    readonly_fields = ("password_hash", "revealed_at", "issued_at", "expires_at", "reset_requested_at")

    def get_readonly_fields(self, request, obj=None):
        # The user must be selectable when creating a credential; afterwards it is fixed.
        if obj is None:
            return ("password_hash", "revealed_at", "issued_at", "expires_at", "reset_requested_at")
        return ("user", "password_hash", "revealed_at", "issued_at", "expires_at", "reset_requested_at")

    @admin.display(description="Student ID")
    def student_id(self, obj):
        return obj.user.student_id

    @admin.display(description="Password")
    def password_state_display(self, obj):
        if obj.password_state == "not_issued":
            return "Not issued"
        if obj.password_state == "revealed":
            return f"Hidden — shown once {obj.revealed_at:%Y-%m-%d %H:%M}" if obj.revealed_at else "Hidden"
        return "Awaiting one-time display"

    def has_add_permission(self, request):
        return False
