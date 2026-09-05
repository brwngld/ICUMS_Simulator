from django.urls import path

from . import views

urlpatterns = [
    path("<uuid:assessment_id>/", views.assessment_take, name="assessment-take"),
    path("attempts/<uuid:attempt_id>/", views.assessment_result, name="assessment-result"),
]
