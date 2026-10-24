"""Admin surface for hybrid learner state.

Content models are authored in the instructor builder; these registrations
expose the verification conditions (until the Tab 4 editor lands) and the
durable learner evidence for staff inspection.
"""
from django.contrib import admin

from .models import LessonAttempt, StepEvent, VerificationCondition


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
    readonly_fields = ("attempt", "step", "kind", "occurred_at")
