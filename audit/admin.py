from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action_code", "actor", "target_type", "target_id")
    list_filter = ("action_code", "created_at")
    search_fields = ("actor__username", "summary", "target_id")
    readonly_fields = (
        "id",
        "actor",
        "action_code",
        "target_type",
        "target_id",
        "summary",
        "metadata",
        "ip_address",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
