from django.urls import path

from . import views

urlpatterns = [
    path("", views.scenario_list, name="scenario-list"),
    path("<uuid:version_id>/", views.scenario_detail, name="scenario-detail"),
    path("<uuid:version_id>/start/", views.scenario_start, name="scenario-start"),
    path("attempts/<uuid:attempt_id>/", views.scenario_workspace, name="scenario-workspace"),
    path("attempts/<uuid:attempt_id>/actions/<uuid:action_id>/", views.scenario_action, name="scenario-action"),
    path("attempts/<uuid:attempt_id>/hint/", views.scenario_hint, name="scenario-hint"),
]
