"""The instructor roster is one row per student, not one per enrolment."""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from learning.models import Module
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from progress.models import ModuleProgress


@pytest.fixture
def roster(db):
    """An instructor, a student in two programmes, and a student in one.

    The two-programme student is half through the first and has not opened the
    second, so the row has to add the two together and lead with the further
    one.
    """
    instructor = User.objects.create_user(username="roster-instructor", email="roster-in@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    student = User.objects.create_user(username="two-programme", email="two@example.test", password="test-password")
    student.groups.add(Group.objects.get(name="Student"))
    single = User.objects.create_user(username="one-programme", email="one@example.test", password="test-password")
    single.groups.add(Group.objects.get(name="Student"))

    built = []
    for index, (name, code, module_count, completed) in enumerate(
        (("Alpha Programme", "alpha", 4, 2), ("Beta Programme", "beta", 2, 0))
    ):
        programme = Programme.objects.create(name=name, code=code)
        version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
        for number in range(1, module_count + 1):
            Module.objects.create(programme_version=version, code=f"{code}-m{number}", title=f"{name} module {number}", order=number, is_published=True)
        enrolment = Enrolment.objects.create(student=student, programme_version=version, enrolled_by=instructor)
        for module in Module.objects.filter(programme_version=version)[:completed]:
            ModuleProgress.objects.create(enrolment=enrolment, module=module, status=ModuleProgress.Status.COMPLETED)
        built.append((programme, version, enrolment))

    gamma = Programme.objects.create(name="Gamma Programme", code="gamma")
    gamma_version = ProgrammeVersion.objects.create(programme=gamma, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    Module.objects.create(programme_version=gamma_version, code="gamma-m1", title="Gamma module 1", order=1, is_published=True)
    single_enrolment = Enrolment.objects.create(student=single, programme_version=gamma_version, enrolled_by=instructor)

    return {
        "instructor": instructor,
        "student": student,
        "single": single,
        "alpha": built[0][2],
        "beta": built[1][2],
        "single_enrolment": single_enrolment,
    }


def rows_of(response):
    return list(response.context["rows"])


@pytest.mark.django_db
def test_a_student_in_two_programmes_is_one_row(client, roster):
    client.force_login(roster["instructor"])
    response = client.get(reverse("instructor-dashboard"))
    rows = rows_of(response)
    assert len(rows) == 2
    by_student = {row["student"].pk: row for row in rows}
    assert by_student[roster["student"].pk]["programme_count"] == 2
    assert by_student[roster["single"].pk]["programme_count"] == 1
    # Two enrolments, but only the two people are listed.
    assert response.content.count(b"<tr data-roster-row") == 2
    assert response.context["stats"]["students"] == 2
    assert response.context["stats"]["total_enrolments"] == 3


@pytest.mark.django_db
def test_the_row_adds_activity_across_the_students_programmes(client, roster):
    client.force_login(roster["instructor"])
    row = next(row for row in rows_of(client.get(reverse("instructor-dashboard"))) if row["student"].pk == roster["student"].pk)
    assert (row["completed_modules"], row["total_modules"]) == (2, 6)
    assert row["percentage"] == 33
    # The row names the programme the student is actually furthest through.
    assert row["primary"]["programme_name"] == "Alpha Programme"


@pytest.mark.django_db
def test_the_row_offers_a_dialog_only_when_there_is_more_than_one_programme(client, roster):
    client.force_login(roster["instructor"])
    content = client.get(reverse("instructor-dashboard")).content
    assert f'id="student-programmes-{roster["student"].pk}"'.encode() in content
    assert f'data-open-programmes="student-programmes-{roster["student"].pk}"'.encode() in content
    assert f'student-programmes-{roster["single"].pk}'.encode() not in content


@pytest.mark.django_db
def test_the_dialog_lists_every_programme_with_its_own_review(client, roster):
    client.force_login(roster["instructor"])
    content = client.get(reverse("instructor-dashboard")).content
    assert b"2 programmes" in content
    for name in (b"Alpha Programme", b"Beta Programme"):
        assert content.count(name) >= 2, f"{name} should appear on the row and in the dialog"
    for enrolment in (roster["alpha"], roster["beta"]):
        assert reverse("instructor-student-detail", args=[enrolment.pk]).encode() in content
    # A multi-programme student has no single Review target left in the row.
    assert content.count("Review →".encode()) == 3  # two in the dialog, one for the single-programme student


@pytest.mark.django_db
def test_a_single_programme_student_keeps_the_plain_row(client, roster):
    client.force_login(roster["instructor"])
    content = client.get(reverse("instructor-dashboard")).content
    assert reverse("instructor-student-detail", args=[roster["single_enrolment"].pk]).encode() in content
    assert b"dash-programme-trigger" in content  # the other student still has one
    assert b"1 programmes" not in content


@pytest.mark.django_db
def test_filters_carry_every_programme_and_status_of_the_student(client, roster):
    roster["beta"].status = Enrolment.Status.WITHDRAWN
    roster["beta"].save(update_fields=("status",))
    client.force_login(roster["instructor"])
    row = next(row for row in rows_of(client.get(reverse("instructor-dashboard"))) if row["student"].pk == roster["student"].pk)
    assert row["programme_filter"] == "Alpha Programme||Beta Programme"
    assert sorted(row["status_filter"].split()) == ["active", "withdrawn"]
    # Searching any of the student's programmes finds the one row.
    assert "beta programme" in row["search_terms"]


@pytest.mark.django_db
def test_two_editions_of_one_programme_are_told_apart(client, roster):
    """The same programme name twice is ordinary — a withdrawn v1 and a live v2."""
    alpha = roster["alpha"].programme_version
    Enrolment.objects.create(student=roster["student"], programme_version=ProgrammeVersion.objects.create(programme=alpha.programme, version=2, status=ProgrammeVersion.Status.PUBLISHED), enrolled_by=roster["instructor"])
    client.force_login(roster["instructor"])
    content = client.get(reverse("instructor-dashboard")).content
    dialog = content.split(b'class="account-dialog dash-programmes-dialog"')[1].split(b"</dialog>")[0]
    assert dialog.count(b"Alpha Programme") == 2
    assert b">v1<" in dialog and b">v2<" in dialog
    assert b"3 programmes" in dialog


@pytest.mark.django_db
def test_a_student_id_shown_once_is_not_repeated_per_enrolment(client, roster):
    """The credential is the student's, so its state appears once for the row."""
    client.force_login(roster["instructor"])
    content = client.get(reverse("instructor-dashboard")).content
    assert content.count(b"Not issued") == 2
