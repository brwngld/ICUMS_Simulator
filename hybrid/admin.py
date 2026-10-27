"""Admin surface for hybrid learner state.

Content models are authored in the instructor builder; these registrations
expose the verification conditions (until the Tab 4 editor lands) and the
durable learner evidence for staff inspection.
"""
from django.contrib import admin

from .models import JourneyVerificationEvidence, LessonAttempt, StepEvent, VerificationCondition


@admin.register(VerificationCondition)
class VerificationConditionAdmin(admin.ModelAdmin):
    list_display = ("step", "kind", "record_kind", "required_status", "order")
    list_filter = ("kind", "record_kind")
    search_fields = ("step__title",)


@admin.register(LessonAttempt)
class LessonAttemptAdmin(admin.ModelAdmin):
    list_display = ("lesson", "enrolment", "current_step", "theory_acknowledged_at", "completed_at")
    list_filter = ("completed_at",)
    search_fields = ("lesson__title", "enrolment__student__username")


@admin.register(StepEvent)
class StepEventAdmin(admin.ModelAdmin):
    list_display = ("attempt", "step", "kind", "occurred_at")
    list_filter = ("kind",)
    readonly_fields = ("attempt", "step", "kind", "occurred_at", "generation")


@admin.register(JourneyVerificationEvidence)
class JourneyVerificationEvidenceAdmin(admin.ModelAdmin):
    list_display = ("journey_step", "condition", "role", "record_kind", "record_id", "verified_at")
    list_filter = ("record_kind",)
    search_fields = ("journey_step__step__title", "condition__step__title", "role__label")
    readonly_fields = tuple(field.name for field in JourneyVerificationEvidence._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
