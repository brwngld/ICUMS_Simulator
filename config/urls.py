"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from accounts.views import LoginView
from core import views as core_views
from scenarios import desk

handler403 = "core.views.permission_denied"

urlpatterns = [
    path("admin/login/", RedirectView.as_view(url="/accounts/login/", permanent=False), name="admin-login-redirect"),
    path('admin/', admin.site.urls),
    path("favicon.ico", RedirectView.as_view(url="/static/image/favicon.ico", permanent=True), name="favicon"),
    # Practice Desk spike: the same desk with its parameters filled in, so it can
    # be opened at /test. Discardable with scenarios/desk.py.
    path("test", desk.test_desk, name="desk-test"),
    path("test/", desk.test_desk, name="desk-test-slash"),
    path("accounts/login/", LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/", include("accounts.urls")),
    path("onboarding/", include("onboarding.urls")),
    path("theory/", include("learning.urls")),
    path("assessments/", include("assessments.urls")),
    path("instructor/", include("instructor_portal.urls")),
    path("practical/", include("scenarios.urls")),
    path("practical/assessment/", include("assessment.urls")),
    path("practical-results/", include("evaluations.urls")),
    path("records/", include("reports.urls")),
    # Theory & Practical (hybrid) system: namespace mounted in Stage 1, pages
    # arrive stage by stage under their own prefix.
    path("hybrid/", include("hybrid.urls")),
    path("media/<path:path>", core_views.media_file, name="media"),
    path("", include("core.urls")),
]

admin.site.site_header = "ICUMS Simulator Administration"
admin.site.site_title = "ICUMS Simulator Admin"
admin.site.index_title = "Training platform administration"
