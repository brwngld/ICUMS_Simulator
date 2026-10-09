from django.shortcuts import redirect


class AdminSuperuserGateMiddleware:
    """Only superusers may use the admin interface. Instructors and students
    are bounced to their home page instead of hitting permission errors."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        gated = request.path.startswith("/admin/") and not request.path.startswith(
            "/admin/password_change/"
        )
        if gated and request.user.is_authenticated and not request.user.is_superuser:
            return redirect("dashboard")
        return self.get_response(request)
