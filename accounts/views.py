from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView as AuthLoginView
from django.db import transaction
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse

from .forms import StudentRegistrationForm
from .models import allocate_student_id


@transaction.atomic
def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = StudentRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.student_id = allocate_student_id(user.first_name)
        user.username = user.student_id
        user.save()
        student_group, _ = Group.objects.get_or_create(name="Student")
        user.groups.add(student_group)
        login(request, user)
        messages.success(request, f"Registration complete. Your Student ID is {user.student_id}.")
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})



class LoginView(AuthLoginView):
    """Django's login view with one adjustment: after signing in,
    administrators land on the Unfold admin dashboard while students and
    tutors land on the learning portal. An explicit ?next= destination
    still wins, exactly as in Django's own view."""

    def get_success_url(self):
        url = self.get_redirect_url()
        if url:
            return url
        if self.request.user.is_staff:
            return reverse("admin:index")
        return resolve_url(settings.LOGIN_REDIRECT_URL)
