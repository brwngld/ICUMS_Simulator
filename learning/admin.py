from django.contrib import admin

from .models import ContentBlock, Lesson, Module, Resource
from assessments.models import LessonCheck


class ContentBlockInline(admin.StackedInline):
    model = ContentBlock
    extra = 0


class LessonCheckInline(admin.TabularInline):
    model = LessonCheck
    extra = 0


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "order", "is_published")
    list_filter = ("is_published", "module")
    prepopulated_fields = {"slug": ("title",)}
    inlines = (ContentBlockInline, LessonCheckInline)

    def has_change_permission(self, request, obj=None):
        return not obj or obj.module.programme_version.status == "draft"

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "programme_version", "order", "is_published", "prerequisite")
    list_filter = ("is_published", "programme_version")
    prepopulated_fields = {"code": ("title",)}

    def has_change_permission(self, request, obj=None):
        return not obj or obj.programme_version.status == "draft"

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "url")
    filter_horizontal = ("lessons",)
