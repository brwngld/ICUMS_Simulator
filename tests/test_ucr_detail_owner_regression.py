
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from accounts.models import SimulatorCredential, User, allocate_student_id
from scenarios.models import UcrDeclaration


@pytest.mark.django_db
def test_ucr_detail_renders_with_owner_column(client):
    """Regression for the OperationalError on /practical/single-window/ucr/<id>/."""
    user = User.objects.create_user(username="ucr-mig", email="ucr@example.test", password="x", first_name="Ucr")
    user.student_id = allocate_student_id("Ucr")
    user.groups.add(Group.objects.get(name="Student"))
    ucr = UcrDeclaration.objects.create(owner=user, ucr_no="TEMPUCRDBG01", status="submitted", regime="10", declarant_code="DBG001")
    credential, _ = SimulatorCredential.objects.get_or_create(user=user)
    credential.issue()
    client.force_login(user)
    session = client.session
    session["simulator_user_id"] = str(user.pk)
    session.save()
    response = client.get(reverse("ucr-detail", args=[ucr.pk]))
    assert response.status_code == 200
    assert "TEMPUCRDBG01" in response.content.decode()
