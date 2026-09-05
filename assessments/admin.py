from django.contrib import admin

from .models import AnswerOption, Assessment, AssessmentItem, LessonCheckResponse, Question, QuestionVersion, TheoryAttempt, TheoryResponse


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 0


@admin.register(QuestionVersion)
class QuestionVersionAdmin(admin.ModelAdmin):
    list_display = ("question", "version", "question_type", "points", "is_published")
    list_filter = ("question_type", "is_published")
    inlines = (AnswerOptionInline,)

    def has_change_permission(self, request, obj=None):
        return not obj or not obj.is_published

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("code",)


class AssessmentItemInline(admin.TabularInline):
    model = AssessmentItem
    extra = 0


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("title", "programme_version", "assessment_type", "module", "pass_percentage", "is_published")
    list_filter = ("assessment_type", "is_published", "programme_version")
    inlines = (AssessmentItemInline,)

    def has_change_permission(self, request, obj=None):
        return not obj or not obj.is_published

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(TheoryAttempt)
class TheoryAttemptAdmin(admin.ModelAdmin):
    list_display = ("enrolment", "assessment", "attempt_number", "status", "percentage", "outcome")
    list_filter = ("status", "outcome", "assessment")
    readonly_fields = [field.name for field in TheoryAttempt._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TheoryResponse)
class TheoryResponseAdmin(admin.ModelAdmin):
    list_display = ("attempt", "question_version", "is_correct", "awarded_score")
    readonly_fields = [field.name for field in TheoryResponse._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LessonCheckResponse)
class LessonCheckResponseAdmin(admin.ModelAdmin):
    list_display = ("enrolment", "lesson_check", "attempt_number", "is_correct", "responded_at")
    readonly_fields = [field.name for field in LessonCheckResponse._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
