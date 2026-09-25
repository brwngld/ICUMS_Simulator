def role_context(request):
    if not request.user.is_authenticated:
        return {"can_access_instructor_portal": False, "can_access_practical": False, "has_active_enrolment": False}
    from progress.models import ProgrammeProgress

    has_active_enrolment = request.user.enrolments.filter(status="active").exists()

    return {
        "can_access_instructor_portal": request.user.is_superuser
        or request.user.groups.filter(name__in=("Instructor", "Administrator")).exists(),
        "can_access_practical": ProgrammeProgress.objects.filter(
            enrolment__student=request.user,
            enrolment__status="active",
            orientation_completed_at__isnull=False,
        ).exists(),
        "has_active_enrolment": has_active_enrolment,
    }


def simulator_review(request):
    """Staff review mode: the student whose simulator work is being viewed (view-only)."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return {"review_target": None}
    from django.contrib.auth import get_user_model

    target_id = request.session.get("simulator_review_user_id")
    if not target_id:
        return {"review_target": None}
    target = get_user_model().objects.filter(pk=target_id).first()
    return {"review_target": target}
