from django import forms

from django.core.exceptions import ValidationError

from assessments.models import AnswerOption, AssessmentItem, Question, QuestionVersion
from learning.models import ContentBlock, Module
from scenarios.models import ScenarioState
from onboarding.models import ProgrammeVersion


class CourseCreateForm(forms.Form):
    name = forms.CharField(max_length=150, label="Course name")


class ModuleCreateForm(forms.Form):
    title = forms.CharField(max_length=180, label="Module title")
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Briefly describe what learners will be able to do after this module.",
    )


class LessonCreateForm(forms.Form):
    title = forms.CharField(max_length=180, label="Lesson title")
    summary = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    concept_heading = forms.CharField(max_length=180, initial="Key concept")
    concept_body = forms.CharField(widget=forms.Textarea(attrs={"rows": 7}), label="Teaching content")
    example_heading = forms.CharField(max_length=180, required=False)
    example_body = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 5}))
    notice_heading = forms.CharField(max_length=180, required=False, label="Important note heading")
    notice_body = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}), label="Important note")
    question_prompt = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Knowledge-check question")
    correct_answer = forms.CharField(max_length=300)
    incorrect_answer_1 = forms.CharField(max_length=300)
    incorrect_answer_2 = forms.CharField(max_length=300)
    incorrect_answer_3 = forms.CharField(max_length=300, required=False)
    explanation = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Shown after the learner answers, so explain why the correct answer is right.",
    )
    add_to_assessment = forms.BooleanField(
        required=False,
        initial=True,
        label="Also add this question to the module assessment",
    )


class PracticalCreateForm(forms.Form):
    title = forms.CharField(max_length=180, label="Practical title")
    area = forms.ChoiceField(choices=(("import", "Import"), ("export", "Export"), ("transit", "Transit"), ("warehouse", "Warehouse")))
    briefing = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), help_text="Describe the fictional task and starting situation.")
    learning_objective = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    assistance_mode = forms.ChoiceField(choices=(("beginner", "Beginner with guidance"), ("intermediate", "Intermediate with limited guidance"), ("advanced", "Advanced without hints")))
    maximum_attempts = forms.IntegerField(required=False, min_value=1, initial=3)
    steps = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 9, "placeholder": "Review documents\nCreate UCR\nCreate BOE\nSubmit declaration\nComplete clearance"}),
        help_text="Enter the required simulated workflow in order, one step per line.",
    )

    def clean_steps(self):
        steps = [line.strip() for line in self.cleaned_data["steps"].splitlines() if line.strip()]
        if len(steps) < 2:
            raise forms.ValidationError("Enter at least two workflow steps.")
        if len(steps) > 30:
            raise forms.ValidationError("Use no more than 30 steps in one practical flow.")
        return steps


class PublishCourseForm(forms.Form):
    programme_version = forms.ModelChoiceField(
        queryset=ProgrammeVersion.objects.none(),
        widget=forms.HiddenInput,
    )

    def __init__(self, *args, **kwargs):
        version = kwargs.pop("version", None)
        super().__init__(*args, **kwargs)
        if version:
            self.fields["programme_version"].queryset = ProgrammeVersion.objects.filter(pk=version.pk, status="draft")


class CourseEditForm(forms.Form):
    name = forms.CharField(max_length=150, label="Course name")


class ModuleEditForm(forms.Form):
    title = forms.CharField(max_length=180, label="Module title")
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Briefly describe what learners will be able to do after this module.",
    )
    prerequisite = forms.ModelChoiceField(
        queryset=Module.objects.none(),
        required=False,
        label="Required before this module",
        help_text="Students must complete the prerequisite module first. Leave empty for no requirement.",
    )

    def __init__(self, module, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module = module
        self.fields["prerequisite"].queryset = Module.objects.filter(
            programme_version=module.programme_version
        ).exclude(pk=module.pk).order_by("order")
        self.fields["title"].initial = module.title
        self.fields["description"].initial = module.description
        self.fields["prerequisite"].initial = module.prerequisite_id

    def clean_prerequisite(self):
        prerequisite = self.cleaned_data.get("prerequisite")
        if prerequisite is None:
            return None
        # Walk the prerequisite chain: this module must never appear in it,
        # or the course would lock itself in a cycle.
        current = prerequisite
        seen = 0
        while current is not None and seen < 50:
            if current.pk == self.module.pk:
                raise forms.ValidationError(
                    "This prerequisite would create a cycle: it (directly or indirectly) already requires this module."
                )
            current = current.prerequisite
            seen += 1
        return prerequisite


class LessonEditForm(forms.Form):
    title = forms.CharField(max_length=180, label="Lesson title")
    summary = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))


BlockFormSet = forms.modelformset_factory(
    ContentBlock,
    fields=("heading", "body"),
    extra=0,
    widgets={"body": forms.Textarea(attrs={"rows": 5})},
)


class LessonCheckEditForm(forms.Form):
    """Edits the single knowledge check attached to a lesson: its prompt,
    explanation, answer labels, and which answer is correct."""

    def __init__(self, question_version, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.question_version = question_version
        # Option fields mirror the question's existing options, so lessons
        # built with any number of answers (two, three, or four) edit cleanly.
        self.options = list(question_version.options.order_by("order"))
        self.fields["prompt"] = forms.CharField(
            label="Knowledge-check question", widget=forms.Textarea(attrs={"rows": 3}), initial=question_version.prompt
        )
        self.fields["explanation"] = forms.CharField(
            label="Explanation", help_text="Shown after the learner answers.",
            widget=forms.Textarea(attrs={"rows": 3}), initial=question_version.explanation,
        )
        choices = []
        for index, option in enumerate(self.options, start=1):
            self.fields[f"option_{index}"] = forms.CharField(
                max_length=300, label=f"Answer {index}", initial=option.label
            )
            choices.append((str(option.pk), f"Answer {index}"))
        correct = next((option.pk for option in self.options if option.is_correct), None)
        self.fields["correct_option"] = forms.ChoiceField(
            label="Correct answer", choices=choices, initial=str(correct) if correct else None
        )

    def save(self):
        data = self.cleaned_data
        question_version = self.question_version
        question_version.prompt = data["prompt"]
        question_version.explanation = data["explanation"]
        question_version.save(update_fields=("prompt", "explanation"))
        for option in self.options:
            option.label = data[f"option_{self.options.index(option) + 1}"]
            option.is_correct = str(option.pk) == data["correct_option"]
            option.save(update_fields=("label", "is_correct"))


class PracticalEditForm(forms.Form):
    briefing = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), help_text="Describe the fictional task and starting situation.")
    learning_objective = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    assistance_mode = forms.ChoiceField(
        choices=(("beginner", "Beginner with guidance"), ("intermediate", "Intermediate with limited guidance"), ("advanced", "Advanced without hints"))
    )
    maximum_attempts = forms.IntegerField(required=False, min_value=1, initial=3)


class ScenarioStateForm(forms.ModelForm):
    binding_route = forms.ChoiceField(
        required=False,
        label="Simulator step target",
        help_text="Approved simulator page this step opens in a separate tab. Leave empty for a text-only step.",
    )
    binding_task = forms.CharField(
        required=False,
        max_length=180,
        label="Task shown to the student",
        help_text="e.g. Submit a UCR declaration in the simulator.",
    )
    binding_verify = forms.ChoiceField(
        required=False,
        label="Verified record and status",
        help_text="What “Check my work” looks for in the student's simulator records.",
    )

    class Meta:
        model = ScenarioState
        fields = ("label", "guidance")
        widgets = {"guidance": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from scenarios.bindings import binding_route_choices, verify_status_choices

        self.fields["binding_route"].choices = binding_route_choices()
        self.fields["binding_verify"].choices = verify_status_choices()
        binding = self.instance.binding if isinstance(self.instance.binding, dict) else {}
        if binding.get("route"):
            self.fields["binding_route"].initial = binding["route"]
            self.fields["binding_task"].initial = binding.get("task", "")
            verify = binding.get("verify") or {}
            if verify.get("record") and verify.get("status"):
                self.fields["binding_verify"].initial = f"{verify['record']}:{verify['status']}"

    def clean(self):
        cleaned = super().clean()
        from scenarios.bindings import validate_binding

        route = cleaned.get("binding_route") or ""
        task = (cleaned.get("binding_task") or "").strip()
        verify_value = cleaned.get("binding_verify") or ""
        if not route and not task and not verify_value:
            self._binding = {}
            return cleaned
        binding = {"route": route, "task": task}
        if verify_value and ":" in verify_value:
            record, status = verify_value.split(":", 1)
            binding["verify"] = {"record": record, "status": status}
        try:
            self._binding = validate_binding(binding)
        except ValidationError as exc:
            for error in getattr(exc, "error_list", [exc]):
                self.add_error("binding_route", error)
            self._binding = {}
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.binding = getattr(self, "_binding", {})
        if commit:
            instance.save()
        return instance


ScenarioStateFormSet = forms.modelformset_factory(
    ScenarioState,
    form=ScenarioStateForm,
    extra=0,
)


class AssessmentSettingsForm(forms.Form):
    title = forms.CharField(max_length=180, label="Assessment title")
    pass_percentage = forms.DecimalField(
        label="Pass mark (%)", min_value=1, max_value=100, initial=70,
        decimal_places=2, max_digits=5,
        help_text="Students pass by scoring at least this percentage.",
    )
    maximum_attempts = forms.IntegerField(
        required=False, min_value=1, initial=3, label="Maximum attempts",
        help_text="Leave empty for unlimited attempts.",
    )
    randomize_questions = forms.BooleanField(required=False, initial=False, label="Show questions in random order")


class AssessmentQuestionForm(forms.Form):
    """Creates or edits one multiple-choice question: prompt, points,
    explanation, and up to four answer options with exactly one correct."""

    prompt = forms.CharField(label="Question", widget=forms.Textarea(attrs={"rows": 3}))
    points = forms.IntegerField(min_value=1, initial=1, label="Points")
    explanation = forms.CharField(
        required=False, label="Explanation",
        help_text="Shown after the learner answers, so explain why the correct answer is right.",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    option_1 = forms.CharField(max_length=300, label="Answer 1")
    option_2 = forms.CharField(max_length=300, label="Answer 2")
    option_3 = forms.CharField(max_length=300, label="Answer 3", required=False)
    option_4 = forms.CharField(max_length=300, label="Answer 4", required=False)
    correct_position = forms.ChoiceField(
        label="Correct answer",
        choices=(("1", "Answer 1"), ("2", "Answer 2"), ("3", "Answer 3"), ("4", "Answer 4")),
        initial="1",
    )

    def clean(self):
        cleaned = super().clean()
        options = [(position, (cleaned.get(f"option_{position}") or "").strip()) for position in range(1, 5)]
        completed = [(position, label) for position, label in options if label]
        if len(completed) < 2:
            raise ValidationError("Add at least two answer options.")
        correct_position = cleaned.get("correct_position")
        if correct_position not in {str(position) for position, _label in completed}:
            raise ValidationError("The correct answer must be one of the completed answer options.")
        cleaned["completed_options"] = completed
        return cleaned

    def save(self, assessment, question_version=None):
        """Create (or, in a draft, update) the question version and its options."""
        from django.utils.text import slugify

        from .views import _unique_slug

        data = self.cleaned_data
        if question_version is None:
            question = Question.objects.create(
                code=_unique_slug(Question, "code", slugify(data["prompt"])[:60] or "assessment-question")
            )
            question_version = QuestionVersion.objects.create(
                question=question, version=1, prompt=data["prompt"],
                explanation=data.get("explanation", ""), points=data["points"],
            )
            last_order = assessment.items.count()
            AssessmentItem.objects.create(assessment=assessment, question_version=question_version, order=last_order + 1)
        else:
            question_version.prompt = data["prompt"]
            question_version.explanation = data.get("explanation", "")
            question_version.points = data["points"]
            question_version.save(update_fields=("prompt", "explanation", "points"))
            question_version.options.all().delete()
        for order, (position, label) in enumerate(data["completed_options"], start=1):
            AnswerOption.objects.create(
                question_version=question_version, label=label,
                is_correct=str(position) == data["correct_position"], order=order,
            )
        return question_version
