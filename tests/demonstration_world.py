"""Shared worlds for the UI 4 demonstration suites.

Two modules cover the same foundation — one for the recording service's rules,
one for the isolation of the records that service will produce — and both start
from the same facts: an instructor, a draft lesson with a live session on it,
and a demonstration record sitting next to an ordinary one. A plain helper
module rather than pytest fixtures, because the tests need to build these worlds
inside threads and inside service calls, not only as test arguments.
"""
from importlib import import_module

from django.conf import settings
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.utils import timezone

from accounts.models import User
from hybrid.models import (
    DemonstrationSession,
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyRecordRole,
    PracticalJourney,
    PracticalStep,
    VerificationCondition,
)
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.demonstration_ucr import next_demonstration_temp_no
from scenarios.models import UcrDeclaration, allocate_ucr_number

SCREEN = "single-window-overview"
SessionEngine = import_module(settings.SESSION_ENGINE)


def instructor(username):
    """A member of the Instructor group — the Studio's canonical authority."""
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x")
    user.groups.add(Group.objects.get_or_create(name="Instructor")[0])
    return user


def programme_version(seed, status):
    programme = Programme.objects.create(
        name=f"{seed} programme", code=seed, learning_track=Programme.Track.HYBRID,
    )
    return ProgrammeVersion.objects.create(programme=programme, version=1, status=status)


def lesson(seed, version, *, with_step=False):
    course = HybridCourse.objects.create(
        programme_version=version, code=f"{seed}-c", title=f"{seed} course", order=1,
    )
    module = HybridModule.objects.create(
        course=course, code=f"{seed}-m", title=f"{seed} module", order=1,
    )
    built = HybridLesson.objects.create(
        module=module, slug=f"{seed}-lesson", title=f"{seed} lesson", order=1,
        summary="Summary.", theory="<p>Theory.</p>",
    )
    step = None
    if with_step:
        step = PracticalStep.objects.create(
            lesson=built, key=f"{seed}-step", title=f"{seed} step",
            instruction="Create the record.", outcome="The record is saved.", screen=SCREEN, order=1,
        )
    return {"course": course, "module": module, "lesson": built, "step": step}


def draft_world(seed, given_instructor=None):
    """An instructor, a draft edition and one lesson — and no session yet.

    Tests that drive ``start_recording`` need this: a world that already holds a
    live session would refuse the second one, which is correct behaviour but not
    what those tests are asserting.
    """
    owner = given_instructor or instructor(f"{seed}-instructor")
    version = programme_version(f"{seed}-edition", ProgrammeVersion.Status.DRAFT)
    built = lesson(f"{seed}-course", version)
    return {"instructor": owner, "version": version, **built}


def recording(seed="demo", instructor=None):
    """A draft lesson plus one live recording session on it."""
    world = draft_world(seed, given_instructor=instructor)
    session = DemonstrationSession.objects.create(
        lesson=world["lesson"], instructor=world["instructor"],
        state=DemonstrationSession.State.RECORDING, started_at=timezone.now(),
    )
    return {**world, "session": session}


def demo_ucr(session, **overrides):
    """A record scoped to a session — the row shape Stage 1B's save service writes."""
    fields = {
        "owner": session.instructor,
        "demonstration_session": session,
        "temp_no": next_demonstration_temp_no(),
        "regime": "CO",
        "exporter_name": "ACME Trading",
    }
    fields.update(overrides)
    return UcrDeclaration.all_objects.create(**fields)


def ordinary_ucr(owner, **overrides):
    fields = {
        "owner": owner,
        "temp_no": allocate_ucr_number(UcrDeclaration.TEMP_PREFIX),
        "regime": "CO",
        "exporter_name": "ACME Trading",
    }
    fields.update(overrides)
    return UcrDeclaration.objects.create(**fields)


def request_for(user, bound=None, method="POST"):
    """A server-side request whose browser holds ``bound`` and nothing else.

    The recording service takes a request, not a session id, precisely because
    the binding is a request fact: this is the shape a forged body cannot
    imitate.
    """
    request = getattr(RequestFactory(), method.lower())("/")
    request.user = user
    request.session = SessionEngine.SessionStore()
    if bound is not None:
        from hybrid import demonstrations

        request.session[demonstrations.ACTIVE_SESSION_KEY] = str(bound)
    return request


def dual_role_world(seed):
    """One user who is both the demonstrating instructor and the enrolled learner.

    Owner filters cannot separate the demonstration row from the ordinary one
    here, so a surface only stays clean if the manager and the ledger
    suppression are doing their job. The journey is built while its edition is
    still a draft — structure changes are refused on a published edition — and
    published before the learner enrolls.
    """
    person = instructor(f"{seed}-dual")
    draft = programme_version(f"{seed}-draft", ProgrammeVersion.Status.DRAFT)
    draft_world = lesson(f"{seed}-draft", draft)
    session = DemonstrationSession.objects.create(
        lesson=draft_world["lesson"], instructor=person,
        state=DemonstrationSession.State.RECORDING, started_at=timezone.now(),
    )
    edition = programme_version(f"{seed}-published", ProgrammeVersion.Status.DRAFT)
    published_world = lesson(f"{seed}-published", edition, with_step=True)
    step = published_world["step"]
    condition = VerificationCondition.objects.create(
        step=step, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="ucr",
        required_status="draft", expected_fields={"exporter_name": "ACME Trading"}, order=1,
    )
    from hybrid import journey_services

    journey = PracticalJourney.objects.create(
        programme_version=edition, course=published_world["course"], code=f"{seed}-journey",
        title=f"{seed} journey", order=1, start_mode=PracticalJourney.StartMode.NEW_RECORD,
    )
    journey_services.assign_step(journey, step)
    role = journey_services.create_record_role(
        journey, "declaration", "Reused declaration", "ucr",
        required=True, creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )
    journey_services.bind_condition(condition, role)
    edition.status = ProgrammeVersion.Status.PUBLISHED
    edition.save(update_fields=("status",))
    enrolment = Enrolment.objects.create(student=person, programme_version=edition)
    return {
        "person": person, "session": session, "step": step, "condition": condition,
        "journey": journey, "role": role, "enrolment": enrolment, "lesson": published_world["lesson"],
        "attempt": journey_services.get_or_create_attempt(enrolment, journey),
    }
