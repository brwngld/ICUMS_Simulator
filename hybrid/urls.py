"""Theory & Practical student routes.

The roadmap is the learning flow's entry point; the workspace serves one
lesson and its attempt endpoints. Every route resolves its own hybrid-track
enrolment via ``hybrid.services`` and never falls back across tracks.
"""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.roadmap, name="hybrid-roadmap"),
    path("lessons/<uuid:lesson_id>/", views.workspace, name="hybrid-workspace"),
    path("attempts/<uuid:attempt_id>/open/<int:step_index>/", views.step_open, name="hybrid-step-open"),
    path("attempts/<uuid:attempt_id>/check/<int:step_index>/", views.step_check, name="hybrid-step-check"),
    path("attempts/<uuid:attempt_id>/advance/<int:step_index>/", views.step_advance, name="hybrid-step-advance"),
    path("attempts/<uuid:attempt_id>/acknowledge-theory/", views.acknowledge_theory, name="hybrid-acknowledge-theory"),
]
