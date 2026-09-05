from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render

from onboarding.models import Enrolment


def _require_instructor(user):
    if not (user.is_superuser or user.groups.filter(name__in=("Instructor", "Administrator")).exists()):
        raise PermissionDenied("Instructor access is required.")


@login_required
def dashboard(request):
    _require_instructor(request.user)
    enrolments = Enrolment.objects.select_related("student", "programme_version__programme").prefetch_related("lesson_progress", "theory_attempts")
    return render(request, "instructor_portal/dashboard.html", {"enrolments": enrolments})


@login_required
def student_detail(request, enrolment_id):
    _require_instructor(request.user)
    enrolment = get_object_or_404(
        Enrolment.objects.select_related("student", "programme_version__programme").prefetch_related(
            "lesson_progress__lesson__module",
            "module_progress__module",
            "theory_attempts__assessment",
            "scenario_attempts__scenario_version__scenario",
        ),
        pk=enrolment_id,
    )
    return render(request, "instructor_portal/student_detail.html", {"enrolment": enrolment})
