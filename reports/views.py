from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Certificate, CompletionRecord
from .services import approve_completion


def _is_instructor(user):
    return user.is_superuser or user.groups.filter(name__in=("Instructor", "Administrator")).exists()


def _authorize_record(user, completion):
    if completion.enrolment.student_id != user.pk and not _is_instructor(user):
        raise PermissionDenied("You cannot view this training record.")


@login_required
def completion_detail(request, completion_id):
    completion = get_object_or_404(
        CompletionRecord.objects.select_related(
            "enrolment__student",
            "enrolment__programme_version__programme",
            "qualifying_evaluation__attempt__scenario_version__scenario",
            "approved_by",
        ),
        pk=completion_id,
    )
    _authorize_record(request.user, completion)
    certificate = Certificate.objects.filter(completion_record=completion).first()
    return render(request, "reports/completion.html", {"completion": completion, "certificate": certificate, "instructor_view": _is_instructor(request.user)})


@login_required
def certificate_detail(request, certificate_id):
    certificate = get_object_or_404(
        Certificate.objects.select_related("completion_record__enrolment__student", "completion_record__enrolment__programme_version__programme"),
        pk=certificate_id,
    )
    _authorize_record(request.user, certificate.completion_record)
    return render(request, "reports/certificate.html", {"certificate": certificate})


@login_required
@require_POST
def completion_approve(request, completion_id):
    completion = get_object_or_404(CompletionRecord, pk=completion_id)
    approve_completion(completion, request.user, request.META.get("REMOTE_ADDR"))
    messages.success(request, "Completion approved and certificate issued.")
    return redirect("completion-detail", completion_id=completion.pk)
