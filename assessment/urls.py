from django.urls import path

from . import views

urlpatterns = [
    path("<int:application_id>/", views.assessment_detail, name="assessment-detail"),
]
