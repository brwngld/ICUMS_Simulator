"""Create a demo Theory & Practical lesson so the workspace is viewable.

Development scaffolding, idempotent: run ``manage.py seed_hybrid_demo`` again
and it reuses the existing rows. The theory copy is deliberately generic
placeholder text — real lesson content is authored in the Stage 3 builder.
"""
from django.core.management.base import BaseCommand
from django.urls import reverse

from hybrid.models import HybridCourse, HybridLesson, HybridModule, PracticalStep
from onboarding.models import Programme, ProgrammeVersion

THEORY_HTML = (
    "<h3>From reading to doing</h3>"
    "<p>Theory & Practical lessons pair a short reading with hands-on work in the ICUMS "
    "simulator. Read the theory panel on the left, then follow the numbered steps in the "
    "live screen on the right.</p>"
    "<h3>How the journey works</h3>"
    "<p>Each step tells you what to do, what you should see when it is done, and offers a "
    "hint if you get stuck. Steps bound to the same screen keep anything you have typed; "
    "moving to a step on another screen opens that screen.</p>"
)

STEPS = [
    ("open-overview", "Open the Single Window", "Open the Single Window overview and find where declarations live.", "The Single Window overview page is open."),
    ("search-declarations", "Search declarations", "Use the declaration search to find existing declarations.", "The declaration search form is open."),
    ("inspect-results", "Inspect the search form", "Look at the search filters available on this screen. (Same screen as the previous step — whatever you typed stays.)", "You can name two filters without leaving the screen."),
    ("open-clearance", "Visit the clearance workspace", "Open the clearance workspace to see where declarations are processed after submission.", "The clearance workspace is open."),
]


class Command(BaseCommand):
    help = "Create the demo hybrid programme, edition and lesson (idempotent)."

    def handle(self, *args, **options):
        programme, _ = Programme.objects.get_or_create(
            code="hybrid-demo",
            defaults={"name": "Theory & Practical demo", "learning_track": Programme.Track.HYBRID},
        )
        programme.learning_track = Programme.Track.HYBRID
        programme.save(update_fields=("learning_track",))
        version, _ = ProgrammeVersion.objects.get_or_create(
            programme=programme, version=1, defaults={"status": ProgrammeVersion.Status.PUBLISHED}
        )
        course, _ = HybridCourse.objects.get_or_create(
            programme_version=version, code="demo-course",
            defaults={"title": "Working the simulator", "order": 1, "is_published": True},
        )
        module, _ = HybridModule.objects.get_or_create(
            course=course, code="demo-module",
            defaults={"title": "Your first guided journey", "order": 1, "is_published": True},
        )
        lesson, _ = HybridLesson.objects.get_or_create(
            module=module, slug="guided-tour",
            defaults={"title": "A guided tour of the workspace", "order": 1, "is_published": True,
                      "summary": "One lesson, several simulator screens: how the Theory & Practical workspace works.",
                      "theory": THEORY_HTML},
        )
        if not lesson.theory:
            lesson.theory = THEORY_HTML
            lesson.save(update_fields=("theory",))
        for order, (key, title, instruction, outcome) in enumerate(STEPS, start=1):
            PracticalStep.objects.get_or_create(
                lesson=lesson, key=key,
                defaults={
                    "title": title, "instruction": instruction, "outcome": outcome,
                    "order": order,
                    "screen": {
                        "open-overview": "single-window-overview",
                        "search-declarations": "single-window-search-ucr",
                        "inspect-results": "",  # same screen: proves the frame is preserved
                        "open-clearance": "clearance-workspace",
                    }[key],
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Demo lesson ready: {reverse('hybrid-workspace', args=[lesson.pk])}"))
