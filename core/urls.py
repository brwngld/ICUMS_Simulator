from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("programmes/", views.my_programmes, name="my-programmes"),
    path("orientation/", views.orientation, name="orientation"),
]
