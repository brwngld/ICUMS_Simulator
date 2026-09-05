from django.contrib import admin

from .models import AssistanceEvent, Scenario, ScenarioAction, ScenarioActionDefinition, ScenarioAttempt, ScenarioDocument, ScenarioState, ScenarioVersion


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "area")
    list_filter = ("area",)
    prepopulated_fields = {"code": ("title",)}


@admin.register(ScenarioVersion)
class ScenarioVersionAdmin(admin.ModelAdmin):
    list_display = ("scenario", "version", "status", "purpose", "assistance_mode", "reference_status")
    list_filter = ("status", "purpose", "assistance_mode", "reference_status")

    def has_change_permission(self, request, obj=None):
        return not obj or obj.status == ScenarioVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(ScenarioState)
class ScenarioStateAdmin(admin.ModelAdmin):
    list_display = ("label", "scenario_version", "order", "is_initial", "is_terminal")
    list_filter = ("scenario_version", "is_initial", "is_terminal")

    def has_change_permission(self, request, obj=None):
        return not obj or obj.scenario_version.status == ScenarioVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(ScenarioActionDefinition)
class ScenarioActionDefinitionAdmin(admin.ModelAdmin):
    list_display = ("label", "scenario_version", "from_state", "to_state", "order")
    list_filter = ("scenario_version",)

    def has_change_permission(self, request, obj=None):
        return not obj or obj.scenario_version.status == ScenarioVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(ScenarioDocument)
class ScenarioDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "document_type", "reference", "scenario_version", "order")
    list_filter = ("scenario_version", "document_type")

    def has_change_permission(self, request, obj=None):
        return not obj or obj.scenario_version.status == ScenarioVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(ScenarioAttempt)
class ScenarioAttemptAdmin(admin.ModelAdmin):
    list_display = ("enrolment", "scenario_version", "attempt_number", "assistance_mode", "status", "current_state", "last_saved_at")
    list_filter = ("status", "assistance_mode", "scenario_version")
    readonly_fields = [field.name for field in ScenarioAttempt._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ScenarioAction)
class ScenarioActionAdmin(admin.ModelAdmin):
    list_display = ("attempt", "sequence", "action_code", "state_before", "state_after", "created_at")
    readonly_fields = [field.name for field in ScenarioAction._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AssistanceEvent)
class AssistanceEventAdmin(admin.ModelAdmin):
    list_display = ("attempt", "kind", "context_code", "created_at")
    readonly_fields = [field.name for field in AssistanceEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
