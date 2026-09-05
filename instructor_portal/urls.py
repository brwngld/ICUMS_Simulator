from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="instructor-dashboard"),
    path("students/<uuid:enrolment_id>/", views.student_detail, name="instructor-student-detail"),
]
