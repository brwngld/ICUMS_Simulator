from django.urls import path

from . import views

urlpatterns = [
    path("", views.roadmap, name="roadmap"),
    path("<slug:module_code>/<slug:lesson_slug>/", views.lesson_detail, name="lesson-detail"),
]
