from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.db import transaction
from django.shortcuts import redirect, render

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

