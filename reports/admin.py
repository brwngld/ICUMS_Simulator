from django.contrib import admin

from .models import Certificate, CompletionPolicy, CompletionRecord


@admin.register(CompletionPolicy)
class CompletionPolicyAdmin(admin.ModelAdmin):
    list_display = ("programme_version", "requires_instructor_approval", "certificate_template_version", "is_active")
    list_filter = ("requires_instructor_approval", "is_active")


@admin.register(CompletionRecord)
class CompletionRecordAdmin(admin.ModelAdmin):
    list_display = ("enrolment", "status", "qualifying_evaluation", "completed_at", "approved_by")
    list_filter = ("status",)
    readonly_fields = [field.name for field in CompletionRecord._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("certificate_number", "completion_record", "status", "issued_at")
    list_filter = ("status",)
    readonly_fields = [field.name for field in Certificate._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
