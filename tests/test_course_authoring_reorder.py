"""Stage 2 — module and lesson reordering within draft courses.

Moves are server-side POSTs, draft-scoped and instructor-gated; positions
compact to 1..N on every move; the student roadmap follows the saved order
(models order by ``order, title``).
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from learning.models import Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion


@pytest.fixture
def instructor(db):
    user = User.objects.create_user(username="order-instructor", email="order@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=user, disclaimer=DisclaimerVersion.objects.create(version=7, title="Stage 2 notice", body="Training only.", is_current=True)
    )
    return user


@pytest.fixture
def ordered_course(db):
    """Draft course: modules Alpha(1), Beta(2), Gamma(3); Alpha has lessons L1..L3."""
    programme = Programme.objects.create(name="Order Programme", code="ordering")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    modules = []
    for index, title in enumerate(["Alpha", "Beta", "Gamma"], start=1):
        module = Module.objects.create(programme_version=version, code=f"module-{index}", title=title, order=index)
        modules.append(module)
    lessons = []
    for index in range(1, 4):
        lessons.append(Lesson.objects.create(module=modules[0], slug=f"lesson-{index}", title=f"Lesson {index}", order=index))
    return {"version": version, "modules": modules, "lessons": lessons}


def _orders(queryset):
    return list(queryset.order_by("order", "title").values_list("title", flat=True))


@pytest.mark.django_db
def test_move_module_up(client, instructor, ordered_course):
    beta = ordered_course["modules"][1]
    client.force_login(instructor)
    response = client.post(reverse("module-move", args=[beta.pk]), {"direction": "up"})
    assert response.status_code == 302
    assert _orders(Module.objects.filter(programme_version=ordered_course["version"])) == ["Beta", "Alpha", "Gamma"]
    assert [m.order for m in Module.objects.order_by("order")] == [1, 2, 3]


@pytest.mark.django_db
def test_move_module_down(client, instructor, ordered_course):
    alpha = ordered_course["modules"][0]
    client.force_login(instructor)
    client.post(reverse("module-move", args=[alpha.pk]), {"direction": "down"})
    assert _orders(Module.objects.filter(programme_version=ordered_course["version"])) == ["Beta", "Alpha", "Gamma"]


@pytest.mark.django_db
def test_first_and_last_boundaries_are_no_ops(client, instructor, ordered_course):
    first = ordered_course["modules"][0]
    last = ordered_course["modules"][2]
    client.force_login(instructor)
    client.post(reverse("module-move", args=[first.pk]), {"direction": "up"})
    client.post(reverse("module-move", args=[last.pk]), {"direction": "down"})
    assert _orders(Module.objects.filter(programme_version=ordered_course["version"])) == ["Alpha", "Beta", "Gamma"]
    assert [m.order for m in Module.objects.order_by("order")] == [1, 2, 3]


@pytest.mark.django_db
def test_invalid_direction_is_a_safe_no_op(client, instructor, ordered_course):
    beta = ordered_course["modules"][1]
    client.force_login(instructor)
    response = client.post(reverse("module-move", args=[beta.pk]), {"direction": "sideways"})
    assert response.status_code == 302
    assert _orders(Module.objects.filter(programme_version=ordered_course["version"])) == ["Alpha", "Beta", "Gamma"]


@pytest.mark.django_db
def test_unknown_module_id_returns_404(client, instructor):
    client.force_login(instructor)
    response = client.post(reverse("module-move", args=["00000000-0000-0000-0000-000000000000"]), {"direction": "up"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_published_course_modules_cannot_be_reordered(client, instructor):
    programme = Programme.objects.create(name="Published Order Programme", code="published-order")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    module = Module.objects.create(programme_version=version, code="p-module", title="Published Module", order=1)
    client.force_login(instructor)
    response = client.post(reverse("module-move", args=[module.pk]), {"direction": "down"})
    assert response.status_code == 404
    module.refresh_from_db()
    assert module.order == 1


@pytest.mark.django_db
def test_student_cannot_reorder(client, ordered_course):
    student = User.objects.create_user(username="order-student", email="order-student@example.test", password="test-password")
    client.force_login(student)
    response = client.post(reverse("module-move", args=[ordered_course["modules"][0].pk]), {"direction": "down"})
    assert response.status_code == 302  # redirected with a message, never an error page
    assert _orders(Module.objects.filter(programme_version=ordered_course["version"])) == ["Alpha", "Beta", "Gamma"]


@pytest.mark.django_db
def test_anonymous_cannot_reorder(client, ordered_course):
    response = client.post(reverse("module-move", args=[ordered_course["modules"][0].pk]), {"direction": "down"})
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_move_lesson_up_and_down_within_module(client, instructor, ordered_course):
    lesson_two = ordered_course["lessons"][1]
    client.force_login(instructor)
    client.post(reverse("lesson-move", args=[lesson_two.pk]), {"direction": "up"})
    assert _orders(Lesson.objects.filter(module=ordered_course["modules"][0])) == ["Lesson 2", "Lesson 1", "Lesson 3"]
    lesson_two.refresh_from_db()
    client.post(reverse("lesson-move", args=[lesson_two.pk]), {"direction": "down"})
    assert _orders(Lesson.objects.filter(module=ordered_course["modules"][0])) == ["Lesson 1", "Lesson 2", "Lesson 3"]
    assert [lesson.order for lesson in Lesson.objects.order_by("order")] == [1, 2, 3]


@pytest.mark.django_db
def test_lesson_moves_do_not_touch_other_modules(client, instructor, ordered_course):
    module_b = ordered_course["modules"][1]
    other_lesson = Lesson.objects.create(module=module_b, slug="b-lesson", title="B Lesson", order=1)
    client.force_login(instructor)
    client.post(reverse("lesson-move", args=[ordered_course["lessons"][0].pk]), {"direction": "down"})
    other_lesson.refresh_from_db()
    assert other_lesson.order == 1
    assert _orders(Lesson.objects.filter(module=module_b)) == ["B Lesson"]


@pytest.mark.django_db
def test_move_compacts_duplicate_and_sparse_orders(client, instructor, ordered_course):
    """Existing messy positions (2, 2, 5) compact deterministically on move."""
    lessons = ordered_course["lessons"]
    Lesson.objects.filter(pk=lessons[0].pk).update(order=2)
    Lesson.objects.filter(pk=lessons[1].pk).update(order=2)
    Lesson.objects.filter(pk=lessons[2].pk).update(order=5)
    client.force_login(instructor)
    client.post(reverse("lesson-move", args=[lessons[2].pk]), {"direction": "up"})
    titles = _orders(Lesson.objects.filter(module=ordered_course["modules"][0]))
    assert titles == ["Lesson 1", "Lesson 3", "Lesson 2"]
    assert [lesson.order for lesson in Lesson.objects.order_by("order", "title")] == [1, 2, 3]


@pytest.mark.django_db
def test_lesson_move_published_course_returns_404(client, instructor, ordered_course):
    version = ordered_course["version"]
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))
    client.force_login(instructor)
    response = client.post(reverse("lesson-move", args=[ordered_course["lessons"][0].pk]), {"direction": "up"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_get_requests_are_rejected(client, instructor, ordered_course):
    client.force_login(instructor)
    response = client.get(reverse("module-move", args=[ordered_course["modules"][0].pk]), {"direction": "down"})
    assert response.status_code == 405
    assert _orders(Module.objects.filter(programme_version=ordered_course["version"])) == ["Alpha", "Beta", "Gamma"]


@pytest.mark.django_db
def test_student_roadmap_follows_saved_order(client, instructor, ordered_course):
    """Reorder modules, then check the student roadmap renders the new sequence."""
    from onboarding.services import current_disclaimer

    student = User.objects.create_user(username="roadmap-student", email="roadmap-student@example.test", password="test-password")
    student.groups.add(Group.objects.get(name="Student"))
    DisclaimerAcceptance.objects.get_or_create(user=student, disclaimer=current_disclaimer())
    Enrolment.objects.create(student=student, programme_version=ordered_course["version"], status="active")
    # The roadmap lists published modules; publishing flips this flag.
    Module.objects.filter(programme_version=ordered_course["version"]).update(is_published=True)

    gamma = ordered_course["modules"][2]
    client.force_login(instructor)
    client.post(reverse("module-move", args=[gamma.pk]), {"direction": "up"})
    client.post(reverse("module-move", args=[gamma.pk]), {"direction": "up"})  # Gamma, Alpha, Beta

    from django.test import Client

    student_client = Client()
    student_client.force_login(student)
    response = student_client.get(reverse("roadmap"))
    assert response.status_code == 200
    rendered_titles = [summary["module"].title for summary in response.context["module_summaries"]]
    assert rendered_titles == ["Gamma", "Alpha", "Beta"]
