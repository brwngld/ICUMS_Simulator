def role_context(request):
    if not request.user.is_authenticated:
        return {"can_access_instructor_portal": False, "can_access_practical": False}
    from progress.models import ProgrammeProgress

    return {
        "can_access_instructor_portal": request.user.is_superuser
        or request.user.groups.filter(name__in=("Instructor", "Administrator")).exists(),
        "can_access_practical": ProgrammeProgress.objects.filter(
            enrolment__student=request.user,
            enrolment__status="active",
            orientation_completed_at__isnull=False,
        ).exists(),
    }
