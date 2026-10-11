from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from unfold.widgets import BASE_INPUT_CLASSES

from .models import User


class StudentRegistrationForm(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    terms_accepted = forms.BooleanField(
        label="I have read and agree to the Terms and Conditions.",
        error_messages={"required": "You must accept the Terms and Conditions to register."},
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        classes = " ".join(BASE_INPUT_CLASSES)
        for name in ("first_name", "last_name", "email", "password1", "password2"):
            self.fields[name].widget.attrs["class"] = classes


class UnfoldLoginForm(AuthenticationForm):
    """Platform login form wearing Unfold's input styling.

    Applies the same widget classes the admin login uses (BASE_INPUT_CLASSES
    from unfold.widgets, so borders, focus rings and dark-mode styles match
    every other Unfold input) without the admin form's staff-only
    restriction — validation semantics are plain Django AuthenticationForm.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        classes = " ".join(BASE_INPUT_CLASSES)
        self.fields["username"].widget.attrs["class"] = classes
        self.fields["password"].widget.attrs["class"] = classes

