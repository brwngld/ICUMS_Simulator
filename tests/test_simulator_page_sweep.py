"""Render sweep across every simulator page a student can open.

A wide smoke net: every parameterless simulator GET route plus the reference
pages and a scratch submitted UCR's pages must render without a server error
under a student with full simulator access. Deeper object flows are covered
by the dedicated suites (UCR, BOE, MDA, consignment, scenario engine).
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import SimulatorCredential, User, allocate_student_id
from scenarios import views as scenario_views
from scenarios.models import UcrDeclaration


@pytest.fixture
def simulator_student(db):
    user = User.objects.create_user(username="sweep-student", email="sweep@example.test", password="test-password", first_name="Sweep")
    user.student_id = allocate_student_id("Sweep")
    user.groups.add(Group.objects.get(name="Student"))
    credential, _ = SimulatorCredential.objects.get_or_create(user=user)
    credential.issue()
    return user


@pytest.fixture
def simulator_client(client, simulator_student):
    client.force_login(simulator_student)
    session = client.session
    session["simulator_user_id"] = str(simulator_student.pk)
    session.save()
    return client


@pytest.mark.django_db
def test_every_simulator_page_renders_without_server_error(simulator_client, simulator_student):
    ucr = UcrDeclaration.objects.create(
        owner=simulator_student, ucr_no="TEMPUCRSWEEP01", status="submitted",
        regime="10", declarant_code="SWP001",
    )
    pages = [
        reverse("simulator-portal"),
        reverse("scenario-list"),
        reverse("cargo-direct-delivery"),
        reverse("cargo-service-request"),
        reverse("clearance-workspace"),
        reverse("clearance-cpc-search"),
        reverse("boe-idf-lookup"),
        reverse("boe-create"),
        reverse("search-boe-declaration"),
        reverse("search-simple-amendment"),
        reverse("search-post-entry-declaration"),
        reverse("create-simple-amendment"),
        reverse("create-post-entry-declaration"),
        reverse("single-window-workspace"),
        reverse("single-window-overview"),
        reverse("single-window-create-ucr"),
        reverse("single-window-search-ucr"),
        reverse("ucr-reference-search"),
        reverse("single-window-search-consignment-application"),
        reverse("single-window-create-consignment-application"),
        reverse("single-window-create-master-application"),
        reverse("single-window-create-opt-in-out"),
        reverse("single-window-search-opt-in-out"),
        reverse("single-window-opt-in-out-detail"),
        reverse("single-window-search-exporter"),
        reverse("single-window-create-exporter"),
        reverse("single-window-create-preparation-application"),
        reverse("single-window-search-preparation-application"),
        reverse("training-service-providers"),
        reverse("ucr-detail", args=[ucr.pk]),
    ]
    for key in sorted(scenario_views.CARGO_REFERENCE_PAGES):
        pages.append(reverse("cargo-reference-page", args=[key]))
    # clearance reference pages accept any slug (the view titles the page from it)
    pages.append(reverse("clearance-reference-page", args=["overview"]))
    # cargo reference pages are keyed
    for key in sorted(scenario_views.CARGO_REFERENCE_PAGES):
        pages.append(reverse("cargo-reference-page", args=[key]))

    failures = []
    for path in pages:
        response = simulator_client.get(path)
        if response.status_code >= 500:
            failures.append(f"{path} -> {response.status_code}")
    assert not failures, "Simulator pages raised server errors:\n" + "\n".join(failures)
