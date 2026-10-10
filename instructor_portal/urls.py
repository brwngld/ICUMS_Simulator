from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="instructor-dashboard"),
    path("courses/", views.course_builder, name="course-builder"),
    path("courses/create/", views.course_create, name="course-create"),
    path("courses/<uuid:version_id>/", views.course_builder_detail, name="course-builder-detail"),
    path("courses/<uuid:version_id>/review/", views.course_review, name="course-review"),
    path("courses/<uuid:version_id>/edit/", views.course_edit, name="course-edit"),
    path("courses/<uuid:version_id>/assessments/create/", views.final_exam_create, name="final-exam-create"),
    path("courses/<uuid:version_id>/publish/", views.course_publish, name="course-publish"),
    path("courses/<uuid:version_id>/modules/create/", views.module_create, name="course-builder-module-create"),
    path("modules/<uuid:module_id>/edit/", views.module_edit, name="module-edit"),
    path("modules/<uuid:module_id>/assessments/create/", views.module_assessment_create, name="module-assessment-create"),
    path("modules/<uuid:module_id>/move/", views.module_move, name="module-move"),
    path("modules/<uuid:module_id>/lessons/new/", views.lesson_builder, name="lesson-builder"),
    path("modules/<uuid:module_id>/lessons/create/", views.lesson_create, name="lesson-create"),
    path("modules/<uuid:module_id>/practicals/new/", views.practical_builder, name="practical-builder"),
    path("lessons/<uuid:lesson_id>/edit/", views.lesson_edit, name="lesson-edit"),
    path("lessons/<uuid:lesson_id>/preview/", views.lesson_preview, name="lesson-preview"),
    path("assessments-mgmt/<uuid:assessment_id>/edit/", views.assessment_edit, name="assessment-edit"),
    path("assessments-mgmt/<uuid:assessment_id>/preview/", views.assessment_preview, name="assessment-preview"),
    path("assessments-mgmt/<uuid:assessment_id>/questions/add/", views.assessment_question_add, name="assessment-question-add"),
    path("assessments-mgmt/<uuid:assessment_id>/questions/<uuid:question_version_id>/edit/", views.assessment_question_edit, name="assessment-question-edit"),
    path("assessments-mgmt/<uuid:assessment_id>/questions/<uuid:question_version_id>/delete/", views.assessment_question_delete, name="assessment-question-delete"),
    path("lessons/<uuid:lesson_id>/move/", views.lesson_move, name="lesson-move"),
    path("practicals/<uuid:scenario_version_id>/edit/", views.practical_edit, name="practical-edit"),
    path("practicals/<uuid:scenario_version_id>/preview/", views.practical_preview, name="practical-preview"),
    path("modules/<uuid:module_id>/practicals/create/", views.practical_create, name="practical-create"),
    path("students/<uuid:enrolment_id>/", views.student_detail, name="instructor-student-detail"),
    path("students/<uuid:user_id>/simulator-credential/issue/", views.simulator_credential_issue, name="simulator-credential-issue"),
]
