"""Forms for the instructor journey organizer.

Record-kind choices come straight from ``scenarios.bindings`` so only
approved simulator record kinds are selectable. The dependency form's
step choices are pre-scoped to one journey's assignments; the services
re-validate everything server-side.
"""
from django import forms

from scenarios.bindings import VERIFY_RECORDS

from .models import JourneyDependency, JourneyRecordRole, JourneyStep, PracticalJourney


class JourneyCreateForm(forms.Form):
    title = forms.CharField(max_length=180, label="Journey title")
    description = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Description",
    )
    start_mode = forms.ChoiceField(
        choices=PracticalJourney.StartMode.choices,
        initial=PracticalJourney.StartMode.NEW_RECORD,
        widget=forms.RadioSelect,
        label="How does the journey start?",
        help_text=(
            "New record: the learner creates the journey's own record. "
            "Existing record: the learner continues an eligible record assigned beforehand."
        ),
    )


class JourneyEditForm(JourneyCreateForm):
    pass


class RecordRoleForm(forms.Form):
    key = forms.SlugField(
        max_length=60, label="Role key",
        help_text="Stable identifier within the journey, e.g. primary-ucr.",
    )
    label = forms.CharField(max_length=180, label="Shown name")
    record_kind = forms.ChoiceField(label="Record kind")
    required = forms.BooleanField(
        required=False, initial=True,
        label="Required for journey completion",
    )
    creation_mode = forms.ChoiceField(
        choices=JourneyRecordRole.CreationMode.choices,
        initial=JourneyRecordRole.CreationMode.NEW,
        widget=forms.RadioSelect,
        label="How the record comes into being",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["record_kind"].choices = [
            (kind, label) for kind, (_model, label) in VERIFY_RECORDS.items()
        ]


class DependencyForm(forms.Form):
    predecessor = forms.ModelChoiceField(queryset=JourneyStep.objects.none(), label="After step")
    dependent = forms.ModelChoiceField(queryset=JourneyStep.objects.none(), label="Enables step")
    dependency_type = forms.ChoiceField(
        choices=JourneyDependency.DependencyType.choices, label="Condition type",
    )
    required_record_role = forms.ModelChoiceField(
        queryset=JourneyRecordRole.objects.none(), required=False, label="Requires record role",
    )

    def __init__(self, journey, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assignments = JourneyStep.objects.filter(journey=journey).select_related("step").order_by("journey_order")
        self.fields["predecessor"].queryset = assignments
        self.fields["dependent"].queryset = assignments
        self.fields["required_record_role"].queryset = JourneyRecordRole.objects.filter(journey=journey)
