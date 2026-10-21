from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("settings/", views.account_settings, name="account-settings"),
    path("credential/", views.account_credential, name="account-credential"),
    path("notifications/", views.notifications, name="account-notifications"),
    path("notifications/read/", views.notifications_mark_read, name="account-notifications-read"),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
]
