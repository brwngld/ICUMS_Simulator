"""Instructor builder routes for the Theory & Practical curriculum.

Included by instructor_portal.urls under ``/instructor/hybrid/``. Every
route is instructor-gated and draft-scoped; the preview is read-only.
"""
from django.urls import path

from . import demonstration_views, instructor_views, reference_views
from . import library_views

urlpatterns = [
    path("", instructor_views.builder_index, name="hybrid-builder"),
    path("programmes/<uuid:programme_id>/", instructor_views.programme_detail, name="hybrid-programme-detail"),
    path("courses/<uuid:course_id>/edit/", instructor_views.course_edit, name="hybrid-course-edit"),
    path("courses/<uuid:course_id>/journeys/", instructor_views.course_journeys, name="hybrid-course-journeys"),
    path("journeys/<uuid:journey_id>/", instructor_views.journey_detail, name="hybrid-journey-detail"),
    path("modules/<uuid:module_id>/edit/", instructor_views.module_edit, name="hybrid-module-edit"),
    path("lessons/<uuid:lesson_id>/edit/", instructor_views.lesson_edit, name="hybrid-lesson-edit"),
    path("lessons/<uuid:lesson_id>/demonstration-studio/", instructor_views.lesson_demonstration_studio, name="hybrid-lesson-demonstration-studio"),
    path("lessons/<uuid:lesson_id>/preview/", instructor_views.lesson_preview, name="hybrid-lesson-preview"),
    # Demonstration recording lifecycle. Server-side authorization only; every
    # route is refused while DEMONSTRATION_RECORDING_ENABLED is off, and none of
    # them touches a simulator record.
    path("demonstration/start/<uuid:lesson_id>/", demonstration_views.demonstration_start, name="hybrid-demonstration-start"),
    path("demonstration/pause/", demonstration_views.demonstration_pause, name="hybrid-demonstration-pause"),
    path("demonstration/resume/", demonstration_views.demonstration_resume, name="hybrid-demonstration-resume"),
    path("demonstration/stop/", demonstration_views.demonstration_stop, name="hybrid-demonstration-stop"),
    path("demonstration/discard/", demonstration_views.demonstration_discard, name="hybrid-demonstration-discard"),
    path("demonstration/session/", demonstration_views.demonstration_session, name="hybrid-demonstration-session"),
    # Stage 2B: converting a stopped recording into draft lesson steps.
    # Instructor-only, draft-lesson-scoped, refused while the flag is off.
    path("demonstration/proposals/<uuid:lesson_id>/<uuid:session_id>/", demonstration_views.demonstration_proposals, name="hybrid-demonstration-proposals"),
    path("demonstration/convert/<uuid:lesson_id>/<uuid:session_id>/", demonstration_views.demonstration_convert, name="hybrid-demonstration-convert"),
    # Stage 2F: reference UCR selection for the Studio.
    path("demonstration/reference/<uuid:lesson_id>/", demonstration_views.demonstration_reference, name="hybrid-demonstration-reference"),
    path("demonstration/reference/<uuid:lesson_id>/select/", demonstration_views.demonstration_reference_select, name="hybrid-demonstration-reference-select"),
    path("demonstration/reference/<uuid:lesson_id>/clear/", demonstration_views.demonstration_reference_clear, name="hybrid-demonstration-reference-clear"),
    # Stage R4-B: the instructor reference library. Instructor-only, JSON,
    # refused while DEMONSTRATION_RECORDING_ENABLED is off.
    path("reference-library/", reference_views.reference_library, name="hybrid-reference-library"),
    path("reference-library/<int:record_id>/", reference_views.reference_detail, name="hybrid-reference-detail"),
    path("reference-library/<int:record_id>/promote/", reference_views.reference_promote, name="hybrid-reference-promote"),
    path("reference-library/<int:record_id>/approve/", reference_views.reference_approve, name="hybrid-reference-approve"),
    path("reference-library/<int:record_id>/retire/", reference_views.reference_retire, name="hybrid-reference-retire"),
    path("reference-library-page/", library_views.reference_library_page, name="hybrid-reference-library-page"),
]
