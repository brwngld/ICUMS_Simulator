from django import forms

from scenarios.country_codes import COUNTRY_CODES
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm as AuthPasswordChangeForm, UserCreationForm
from unfold.widgets import BASE_INPUT_CLASSES

#: The shared Unfold input look, for places that hand-write a field instead
#: of going through a form (the Settings page's placeholder dropdowns).
INPUT_CLASSES = " ".join(BASE_INPUT_CLASSES)

from .models import RenewalReason, User, UserPreference


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



class ProfileForm(forms.ModelForm):
    """The Settings page: the learner's own account details."""

    country = forms.ChoiceField(
        choices=[("", "-- Select One --")] + list(COUNTRY_CODES),
        required=False,
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "organisation", "certificate_name", "country")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        classes = " ".join(BASE_INPUT_CLASSES)
        for name in self.fields:
            self.fields[name].widget.attrs["class"] = classes


class PreferencesForm(forms.ModelForm):
    """The Settings page's choice dropdowns: display format and reminders."""

    class Meta:
        model = UserPreference
        fields = ("language", "timezone", "date_format", "expiry_reminder_days")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].widget.attrs["class"] = INPUT_CLASSES
        self.fields["expiry_reminder_days"].widget.attrs["aria-label"] = "Expiry reminder timing"
        self.fields["language"].widget.attrs["aria-label"] = "Language"
        self.fields["timezone"].widget.attrs["aria-label"] = "Time zone"
        self.fields["date_format"].widget.attrs["aria-label"] = "Date format"


class CredentialRenewalForm(forms.Form):
    """The learner's renewal request: why, plus an optional note to the instructor."""

    reason = forms.ChoiceField(
        choices=RenewalReason.choices,
        widget=forms.Select(attrs={"aria-label": "Reason"}),
    )
    note = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(
            attrs={"rows": 3, "aria-label": "Message to instructor", "placeholder": "e.g. I have a practical session on Monday."}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].widget.attrs["class"] = INPUT_CLASSES


class PasswordChangeForm(AuthPasswordChangeForm):
    """The Settings dialog's change-password form, wearing the platform inputs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        classes = " ".join(BASE_INPUT_CLASSES)
        for field in self.fields.values():
            field.widget.attrs["class"] = classes
