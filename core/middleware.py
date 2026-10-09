from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect


class AdminSuperuserGateMiddleware:
    """Only superusers may use the admin interface. Instructors and students
    are bounced to their home page instead of hitting permission errors —
    except when they log out, which must always work."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith("/admin/")
            and request.user.is_authenticated
            and not request.user.is_superuser
        ):
            if request.path == "/admin/logout/" and request.method == "POST":
                auth_logout(request)
                return redirect("/")
            return redirect("dashboard")
        return self.get_response(request)
