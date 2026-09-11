from django.urls import path

from . import views

urlpatterns = [
    path("completion/<uuid:completion_id>/", views.completion_detail, name="completion-detail"),
    path("completion/<uuid:completion_id>/approve/", views.completion_approve, name="completion-approve"),
    path("certificates/<uuid:certificate_id>/", views.certificate_detail, name="certificate-detail"),
]
