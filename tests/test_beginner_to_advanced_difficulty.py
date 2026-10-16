import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from onboarding.models import Programme, ProgrammeVersion


@pytest.mark.django_db
def test_course_overview_editor_offers_beginner_to_advanced(client, django_user_model):
    instructor = django_user_model.objects.create_user(username="difficulty-instructor", password="test-password")
    group, _ = Group.objects.get_or_create(name="Instructor")
    instructor.groups.add(group)
    programme = Programme.objects.create(name="Full Path", code="full-path")
    version = ProgrammeVersion.objects.create(programme=programme, version=1)
    client.force_login(instructor)

    response = client.get(reverse("course-edit", args=[version.pk]) + "?tab=settings")

    assert response.status_code == 200
    assert b'value="beginner-advanced"' in response.content
    assert b"Beginner to Advanced" in response.content
