from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class StudentRegistrationForm(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password1", "password2")

