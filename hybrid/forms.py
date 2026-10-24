"""Instructor authoring forms for the Theory & Practical builder.

Screen choices come straight from ``scenarios.bindings`` at form-build time,
so an instructor can only ever pick a developer-approved screen of any
supported workflow — free-text screens, selectors or expressions have no
field to live in. The theory form uses the ``form`` prefix on purpose: the
shared rich-text editor binds textareas whose ids match ``id_form-*-body``.
"""
from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import construct_instance

from onboarding.models import Programme
from scenarios.bindings import binding_route_choices, verify_status_choices

from .models import HybridModule, PracticalStep, VerificationCondition


class CourseCreateForm(forms.Form):
    programme = forms.ModelChoiceField(
        queryset=Programme.objects.none(),
        label="Programme",
        help_text="Only Theory & Practical programmes are listed. A draft edition is reused or created automatically.",
    )
    title = forms.CharField(max_length=180, label="Course title")
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Shown to instructors in the builder; learner display copy arrives with publication.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["programme"].queryset = Programme.objects.filter(
            learning_track=Programme.Track.HYBRID, is_active=True
        ).order_by("name")


class CourseEditForm(forms.Form):
    title = forms.CharField(max_length=180, label="Course title")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class ModuleForm(forms.Form):
    title = forms.CharField(max_length=180, label="Module title")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class LessonDetailsForm(forms.Form):
    title = forms.CharField(max_length=180, label="Lesson title")
    summary = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Shown at the top of the lesson workspace.",
    )


class TheoryForm(forms.Form):
    """The lesson's one continuous theory reading (a single rich-text body)."""

    body = forms.CharField(
        required=False,
        label="Theory reading",
        widget=forms.Textarea(attrs={"rows": 16}),
        help_text="One continuous reading. Headings inside the text become the section markers learners see.",
    )

    def __init__(self, *args, body=None, **kwargs):
        # The "form" prefix gives the textarea id_form-body, which the shared
        # rich-text editor enhances.
        kwargs.setdefault("prefix", "form")
        super().__init__(*args, **kwargs)
        if body is not None:
            self.initial["body"] = body


class StepForm(forms.ModelForm):
    class Meta:
        model = PracticalStep
        fields = ("title", "instruction", "outcome", "hint", "screen")
        widgets = {
            "instruction": forms.Textarea(attrs={"rows": 3}),
            "outcome": forms.Textarea(attrs={"rows": 2}),
            "hint": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Built per form so a registry update is reflected without a restart
        # baking stale choices into a class-level field.
        self.fields["screen"] = forms.ChoiceField(
            required=False,
            choices=binding_route_choices(),
            label="Simulator screen",
            help_text="Developer-approved screens only. Blank keeps whatever screen the lesson already shows.",
        )


class StepFormSet(forms.modelformset_factory(PracticalStep, form=StepForm, extra=0)):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "steps")
        super().__init__(*args, **kwargs)


class VerificationConditionForm(forms.ModelForm):
    """Author one server-verified condition for a practical step.

    The record-and-status pair comes straight from the shared registry's
    flattened choices, and expected saved values are a JSON object of scalars
    validated against the record model — the same shape the Practical
    Builder's binding editor accepts, with no free-text route, selector or
    expression anywhere.
    """

    record_status = forms.ChoiceField(
        required=False,
        label="Record and status",
        help_text="Saved-record conditions only: which approved record, in which status.",
    )
    expected_fields = forms.JSONField(
        required=False,
        label="Expected saved values",
        help_text=(
            'A JSON object of exact saved values, e.g. {"exporter_name": "ACME Trading"}. '
            "Text, numbers, booleans or null only; every field name is checked against the record model."
        ),
    )

    def _post_clean(self):
        # clean() has already validated the instance against the registries
        # and reported its per-field errors on this form's own fields (the
        # model's record_kind/required_status pair is merged into the single
        # record_status field). The default post-clean would re-run the
        # model's full_clean and re-raise those errors under names this form
        # deliberately does not carry.
        opts = self._meta
        self.instance = construct_instance(self, self.instance, opts.fields, opts.exclude)

    class Meta:
        model = VerificationCondition
        fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"] = forms.ChoiceField(
            choices=VerificationCondition.Kind.choices, label="Condition type",
        )
        self.fields["record_status"].choices = verify_status_choices()
        if self.instance.pk and self.instance.kind == VerificationCondition.Kind.SAVED_RECORD:
            self.initial["record_status"] = f"{self.instance.record_kind}:{self.instance.required_status}"
            self.initial["expected_fields"] = self.instance.expected_fields

    def clean(self):
        cleaned = super().clean()
        instance = self.instance
        instance.kind = cleaned.get("kind") or ""
        if instance.kind == VerificationCondition.Kind.SAVED_RECORD:
            record_kind, _, status = (cleaned.get("record_status") or "").partition(":")
            instance.record_kind = record_kind
            instance.required_status = status
            instance.expected_fields = cleaned.get("expected_fields") or {}
        else:
            instance.record_kind = ""
            instance.required_status = ""
            instance.expected_fields = {}
        try:
            # The step is already on the instance; everything else is validated
            # against the registries here, before anything is saved.
            instance.full_clean(exclude={"step"})
        except ValidationError as exc:
            field_errors: dict = {}
            for field, messages in exc.message_dict.items():
                if field in ("record_kind", "required_status"):
                    field_errors.setdefault("record_status", []).extend(messages)
                elif field in self.fields:
                    field_errors[field] = messages
                else:
                    field_errors.setdefault("__all__", []).extend(messages)
            raise forms.ValidationError(field_errors)
        return cleaned
