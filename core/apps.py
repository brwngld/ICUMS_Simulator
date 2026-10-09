import types

from django.apps import AppConfig
from django.contrib import admin


def _interface_has_permission(admin_site, request):
    """Any active authenticated user may use the Unfold interface shell.

    This is a presentation-layer gate only: it never grants model
    permissions. What each account sees in the navigation is decided by
    core.admin_dashboard.sidebar_navigation, and every admin view is still
    protected by Django's own model permission checks.
    """
    return request.user.is_active


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # django-unfold replaces admin.site with its own site and only builds
        # the sidebar for staff users. Patch that check so non-staff accounts
        # (students) also get the interface shell — without granting them any
        # admin permissions (model access is still enforced per view).
        admin.site.has_permission = types.MethodType(
            _interface_has_permission, admin.site
        )
