from django.contrib import admin

from .models import LessonProgress, ModuleProgress, ProgrammeProgress


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("enrolment", "lesson", "completed_at", "updated_at")
    list_filter = ("completed_at", "lesson__module")


@admin.register(ModuleProgress)
class ModuleProgressAdmin(admin.ModelAdmin):
    list_display = ("enrolment", "module", "status", "completed_at")
    list_filter = ("status", "module")


@admin.register(ProgrammeProgress)
class ProgrammeProgressAdmin(admin.ModelAdmin):
    list_display = ("enrolment", "theory_completed_at", "orientation_unlocked_at", "orientation_completed_at")
