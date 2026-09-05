from django.contrib import admin

from .models import CriterionResult, EvaluationRevision, InstructorFeedback, PracticalEvaluation, RemediationRecommendation, Rubric, RubricCriterion, RubricVersion


@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ("code", "title")
    prepopulated_fields = {"code": ("title",)}


class RubricCriterionInline(admin.StackedInline):
    model = RubricCriterion
    extra = 0


@admin.register(RubricVersion)
class RubricVersionAdmin(admin.ModelAdmin):
    list_display = ("rubric", "version", "scenario_version", "status", "pass_percentage", "is_demonstration")
    list_filter = ("status", "is_demonstration")
    inlines = (RubricCriterionInline,)

    def has_change_permission(self, request, obj=None):
        return not obj or obj.status == RubricVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(PracticalEvaluation)
class PracticalEvaluationAdmin(admin.ModelAdmin):
    list_display = ("attempt", "system_percentage", "system_outcome", "elapsed_seconds", "evaluated_at")
    list_filter = ("system_outcome", "rubric_version")
    readonly_fields = [field.name for field in PracticalEvaluation._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyEvidenceAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for read_only_model in (CriterionResult, RemediationRecommendation, EvaluationRevision, InstructorFeedback):
    admin.site.register(read_only_model, ReadOnlyEvidenceAdmin)
