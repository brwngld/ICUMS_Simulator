from django.contrib import admin

from .models import LessonProgress, ModuleProgress, ProgrammeProgress
from core.admin_pagination import ModelAdmin


@admin.register(LessonProgress)
class LessonProgressAdmin(ModelAdmin):
    list_display = ("enrolment", "lesson", "completed_at", "updated_at")
    list_filter = ("completed_at", "lesson__module")


@admin.register(ModuleProgress)
class ModuleProgressAdmin(ModelAdmin):
    list_display = ("enrolment", "module", "status", "completed_at")
    list_filter = ("status", "module")


@admin.register(ProgrammeProgress)
class ProgrammeProgressAdmin(ModelAdmin):
    list_display = ("enrolment", "theory_completed_at", "orientation_unlocked_at", "orientation_completed_at")
