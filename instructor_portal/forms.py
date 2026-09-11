from django import forms

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
