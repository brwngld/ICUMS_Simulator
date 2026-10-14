from django.urls import path

from . import views

urlpatterns = [
    path("", views.roadmap, name="roadmap"),
    path("<slug:module_code>/", views.module_overview, name="module-overview"),
    path("<slug:module_code>/<slug:lesson_slug>/", views.lesson_detail, name="lesson-detail"),
    path("<slug:module_code>/<slug:lesson_slug>/<slug:section>/", views.lesson_detail, name="lesson-section"),
]
