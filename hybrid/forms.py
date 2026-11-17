"""Instructor authoring forms for the Theory & Practical builder.

Screen choices come straight from ``scenarios.bindings`` at form-build time,
so an instructor can only ever pick a developer-approved screen of any
supported workflow — free-text screens, selectors or expressions have no
field to live in. The theory form uses the ``form`` prefix on purpose: the
shared rich-text editor binds textareas whose ids match ``id_form-*-body``.
"""
from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import construct_instance

from onboarding.models import Programme
from scenarios.bindings import (
    binding_route_choices,
    checkable_fields,
    verify_field_choices,
    verify_status_choices,
)

from .models import (
    HybridLesson,
    HybridModule,
    KnowledgeCheck,
    LessonMaterial,
    PracticalStep,
    VerificationCondition,
)

#: Empty saved-value rows offered with every condition, so two expectations can
#: be authored in one save without the page having to grow rows by script.
_BLANK_VALUE_ROWS = 2
#: Ceiling on the rows one condition can carry, so a crafted POST cannot ask the
#: server to build an unbounded field set.
_MAX_VALUE_ROWS = 12

_TRUE_WORDS = {"true", "yes", "1", "on"}
_FALSE_WORDS = {"false", "no", "0", "off"}


def _display_value(value):
    """How a stored expectation is typed back into the form."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _coerce_value(value_kind, raw):
    """Convert typed text to the value the record's column actually holds.

    The journey engine compares expectations with plain equality against the
    saved attribute, so ``"12"`` checked against a number column would fail
    forever. Conversion happens here instead of in the learner's feedback.
    """
    if value_kind == "boolean":
        lowered = raw.lower()
        if lowered in _TRUE_WORDS:
            return True
        if lowered in _FALSE_WORDS:
            return False
        raise ValidationError("Answer yes or no for this flag.")
    if value_kind == "number":
        try:
            return int(raw)
        except ValueError:
            raise ValidationError("Enter a whole number for this value.") from None
    return raw


class ProgrammeCreateForm(forms.ModelForm):
    """Open a Theory & Practical programme from inside the builder.

    Only the two identifying fields are asked for; the learning track is fixed
    by the view, so a builder-created programme can never land in the theory
    system, and every other programme field keeps its existing default.
    """

    class Meta:
        model = Programme
        fields = ("name", "code")
        labels = {"name": "Programme name", "code": "Programme code"}


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
    kind = forms.ChoiceField(
        choices=HybridLesson.Kind.choices,
        initial=HybridLesson.Kind.INTERACTIVE_PRACTICAL,
        label="Lesson type",
        required=False,
        help_text=(
            "Interactive Practical lessons are built in the Demonstration Studio. "
            "Guided Material Study lessons are written in the lesson editor."
        ),
    )
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


class MaterialUploadForm(forms.Form):
    """Attach one supporting document to a guided lesson.

    Only real documents and images are accepted: the extension whitelist keeps
    script or executable files out of the curriculum media tree, and the size
    cap keeps an oversized upload from stalling the request.
    """

    ALLOWED_EXTENSIONS = {
        ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv",
        ".png", ".jpg", ".jpeg", ".gif", ".webp",
    }
    MAX_BYTES = 25 * 1024 * 1024

    file = forms.FileField(label="Document or image")

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if Path(uploaded.name).suffix.lower() not in self.ALLOWED_EXTENSIONS:
            raise ValidationError("Attach a document or image (PDF, Office, CSV, PNG, JPG, GIF or WebP).")
        if uploaded.size > self.MAX_BYTES:
            raise ValidationError("That file is larger than the 25 MB limit.")
        return uploaded


class KnowledgeCheckForm(forms.ModelForm):
    """Author one optional knowledge check under a guided lesson's reading.

    The four option slots and the correct-answer radio post with the question,
    so a check a learner could not answer never saves: a prompt, at least two
    non-empty options, and a correct answer that is one of them are all
    required. The row is born blank (Add knowledge check) and stays blank
    until this form accepts it, mirroring how activities are born.
    """

    OPTION_SLOTS = 4

    class Meta:
        model = KnowledgeCheck
        fields = ()

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, instance=instance, **kwargs)
        self.fields["prompt"] = forms.CharField(label="Question", widget=forms.TextInput)
        for slot in range(self.OPTION_SLOTS):
            self.fields[f"option_{slot}"] = forms.CharField(label=f"Option {slot + 1}", required=False)
        self.fields["answer"] = forms.ChoiceField(
            label="Correct answer",
            choices=[(str(slot), f"Option {slot + 1}") for slot in range(self.OPTION_SLOTS)],
            initial="0",
            widget=forms.RadioSelect,
        )
        if instance is not None:
            # The fields are declared, not model fields, so the saved check is
            # slotted into them here rather than by the ModelForm machinery.
            options = list(instance.options or [])
            self.fields["prompt"].initial = instance.prompt
            for slot in range(self.OPTION_SLOTS):
                self.fields[f"option_{slot}"].initial = options[slot] if slot < len(options) else ""
            answer = instance.answer_index if 0 <= instance.answer_index < self.OPTION_SLOTS else 0
            self.fields["answer"].initial = str(answer)

    def clean(self):
        cleaned = super().clean()
        options = [cleaned.get(f"option_{slot}", "") for slot in range(self.OPTION_SLOTS)]
        # Errors attach to fields, not the form: the editor card renders field
        # groups only, so a form-wide error would refuse the save invisibly.
        if sum(1 for text in options if text.strip()) < 2:
            self.add_error("option_0", "Give the check at least two options a learner could choose between.")
        answer = int(cleaned.get("answer", "0"))
        if not options[answer].strip():
            self.add_error("answer", "Mark a filled-in option as the correct answer.")
        cleaned["options"] = options
        cleaned["answer_index"] = answer
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.prompt = self.cleaned_data["prompt"]
        instance.options = self.cleaned_data["options"]
        instance.answer_index = self.cleaned_data["answer_index"]
        if commit:
            instance.save()
        return instance


class StepForm(forms.ModelForm):
    """One practical activity.

    Each activity card posts its own step form, prefixed with the step's id,
    so editing one activity never validates or rewrites its siblings.
    """

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


class VerificationConditionForm(forms.ModelForm):
    """Author one server-verified condition for a practical step.

    The record-and-status pair and each exact saved value come straight from
    the shared registry as a select and a text box, so an instructor never
    writes JSON: a number is stored as a number, a flag as a flag, and every
    column name is one the record actually has. Clearing a row's dropdown is
    how a saved value stops being checked.
    """

    record_status = forms.ChoiceField(
        required=False,
        label="Record and status",
        help_text="Saved-record conditions only: which approved record, in which status.",
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
        stored = self.instance.expected_fields
        self.stored = dict(stored) if isinstance(stored, dict) else {}
        self.original_keys = sorted(self.stored)
        self.fields["kind"] = forms.ChoiceField(
            choices=VerificationCondition.Kind.choices, label="Condition type",
            initial=self.instance.kind or None,
        )
        self.fields["record_status"].choices = verify_status_choices()
        if self.instance.pk and self.instance.kind == VerificationCondition.Kind.SAVED_RECORD:
            # Blank until the instructor picks one: an empty half of the pair
            # would otherwise be typed back as ":", which matches no option.
            if self.instance.record_kind and self.instance.required_status:
                self.initial["record_status"] = f"{self.instance.record_kind}:{self.instance.required_status}"
        # A bound form honours the row count the page was built with; extra rows
        # would report errors nobody can see, and a stale page must not delete
        # values it never displayed. The count travels as a field of this form,
        # so several conditions on one page keep their own counts under their
        # own prefixes.
        self.row_count = self._bound_row_count() if self.is_bound else len(self.original_keys) + _BLANK_VALUE_ROWS
        self.fields["value_rows"] = forms.CharField(
            required=False, widget=forms.HiddenInput(),
        )
        self.initial["value_rows"] = str(self.row_count)
        for index in range(self.row_count):
            self.fields[f"check_{index}"] = forms.ChoiceField(
                required=False,
                choices=verify_field_choices(),
                label="Saved value",
                help_text="A column of the record this condition checks, or “— None —” to stop checking it.",
            )
            self.fields[f"value_{index}"] = forms.CharField(
                required=False,
                label="Expected saved value",
                help_text="Exactly what the simulator must have saved.",
            )
        for index, column in enumerate(self.original_keys[: self.row_count]):
            self.initial[f"check_{index}"] = f"{self.instance.record_kind}:{column}"
            self.initial[f"value_{index}"] = _display_value(self.stored[column])

    def _bound_row_count(self):
        try:
            count = int(self.data.get(self.add_prefix("value_rows"), ""))
        except (TypeError, ValueError):
            count = 0
        return max(0, min(count, _MAX_VALUE_ROWS))

    @property
    def saved_value_rows(self):
        """The paired dropdowns and text boxes, in page order.

        Not named ``value_rows``: that is the hidden field carrying the count,
        and a template asking the form for ``value_rows`` gets the field.
        """
        return [
            {"check": self[f"check_{index}"], "value": self[f"value_{index}"]}
            for index in range(self.row_count)
        ]

    def _clean_value_rows(self, record_kind):
        """Rebuild the expected-values dict from the submitted rows."""
        values = {
            column: self.stored[column]
            for column in self.original_keys[self.row_count:]
        }
        errors = {}
        for index in range(self.row_count):
            chosen = str(self.cleaned_data.get(f"check_{index}") or "")
            raw = str(self.cleaned_data.get(f"value_{index}") or "").strip()
            if not chosen:
                if raw:
                    errors[f"value_{index}"] = "Choose which saved value this row checks."
                continue
            chosen_kind, _, column = chosen.partition(":")
            if chosen_kind != record_kind:
                errors[f"check_{index}"] = "Choose a value saved on the same kind of record as this condition."
                continue
            value_kind = dict(
                (name, kind) for name, _label, kind in checkable_fields(chosen_kind)
            ).get(column)
            if not raw:
                errors[f"value_{index}"] = "Enter the value this saved column must have."
                continue
            try:
                values[column] = _coerce_value(value_kind, raw)
            except ValidationError as exc:
                errors[f"value_{index}"] = list(exc.messages)
        return values, errors

    def clean(self):
        cleaned = super().clean()
        instance = self.instance
        instance.kind = cleaned.get("kind") or ""
        row_errors = {}
        if instance.kind == VerificationCondition.Kind.SAVED_RECORD:
            record_kind, _, status = (cleaned.get("record_status") or "").partition(":")
            instance.record_kind = record_kind
            instance.required_status = status
            if record_kind:
                instance.expected_fields, row_errors = self._clean_value_rows(record_kind)
            else:
                instance.expected_fields = dict(self.stored)
        else:
            instance.record_kind = ""
            instance.required_status = ""
            instance.expected_fields = {}
        field_errors: dict = {}
        try:
            # The step is already on the instance; everything else is validated
            # against the registries here, before anything is saved.
            instance.full_clean(exclude={"step"})
        except ValidationError as exc:
            for field, message_list in exc.message_dict.items():
                if field in ("record_kind", "required_status"):
                    field_errors.setdefault("record_status", []).extend(message_list)
                elif field in self.fields:
                    field_errors[field] = message_list
                else:
                    field_errors.setdefault("__all__", []).extend(message_list)
        field_errors.update(row_errors)
        if field_errors:
            raise forms.ValidationError(field_errors)
        return cleaned
