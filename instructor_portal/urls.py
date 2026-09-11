from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="instructor-dashboard"),
    path("courses/", views.course_builder, name="course-builder"),
    path("courses/create/", views.course_create, name="course-create"),
    path("courses/<uuid:version_id>/", views.course_builder_detail, name="course-builder-detail"),
    path("courses/<uuid:version_id>/review/", views.course_review, name="course-review"),
    path("courses/<uuid:version_id>/publish/", views.course_publish, name="course-publish"),
    path("courses/<uuid:version_id>/modules/create/", views.module_create, name="course-builder-module-create"),
    path("modules/<uuid:module_id>/lessons/new/", views.lesson_builder, name="lesson-builder"),
    path("modules/<uuid:module_id>/lessons/create/", views.lesson_create, name="lesson-create"),
    path("modules/<uuid:module_id>/practicals/new/", views.practical_builder, name="practical-builder"),
    path("modules/<uuid:module_id>/practicals/create/", views.practical_create, name="practical-create"),
    path("students/<uuid:enrolment_id>/", views.student_detail, name="instructor-student-detail"),
    path("students/<uuid:user_id>/simulator-credential/issue/", views.simulator_credential_issue, name="simulator-credential-issue"),
]
