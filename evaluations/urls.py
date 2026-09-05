from django.urls import path

from . import views

urlpatterns = [
    path("<uuid:evaluation_id>/", views.evaluation_detail, name="practical-evaluation"),
    path("<uuid:evaluation_id>/override/", views.evaluation_override, name="practical-evaluation-override"),
    path("<uuid:evaluation_id>/feedback/", views.evaluation_feedback, name="practical-evaluation-feedback"),
]
