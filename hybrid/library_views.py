"""Instructor Reference Library page (Stage R4-D1).

Serves the reference library UI inside the Django Unfold instructor portal,
backed by the R4-B lifecycle endpoints and the R4-A protected model fields.
"""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from instructor_portal.views import _require_instructor

from . import demonstrations


@login_required
def reference_library_page(request):
    """The instructor Reference Library page."""
    _require_instructor(request.user)
    return render(request, "hybrid/reference_library.html", {
        "title": "Reference Library",
        "csrf_token": request.META.get("CSRF_COOKIE", ""),
    })
