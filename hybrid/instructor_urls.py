"""Instructor builder routes for the Theory & Practical curriculum.

Included by instructor_portal.urls under ``/instructor/hybrid/``. Every
route is instructor-gated and draft-scoped; the preview is read-only.
"""
from django.urls import path

from . import instructor_views

urlpatterns = [
    path("", instructor_views.builder_index, name="hybrid-builder"),
    path("courses/<uuid:course_id>/edit/", instructor_views.course_edit, name="hybrid-course-edit"),
    path("modules/<uuid:module_id>/edit/", instructor_views.module_edit, name="hybrid-module-edit"),
    path("lessons/<uuid:lesson_id>/edit/", instructor_views.lesson_edit, name="hybrid-lesson-edit"),
    path("lessons/<uuid:lesson_id>/preview/", instructor_views.lesson_preview, name="hybrid-lesson-preview"),
]
