"""UCR clone must copy document attachments after the draft is saved.

Regression: cloning a UCR whose source carried document attachments crashed
with "save() prohibited to prevent data loss due to unsaved related object
'ucr'" because the attachments were written before the clone had a primary
key.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from accounts.models import SimulatorCredential, User, allocate_student_id
from scenarios.models import UcrDeclaration, UcrDocumentAttachment


@pytest.fixture
def simulator_student(db):
    user = User.objects.create_user(username="clone-student", email="clone@example.test", password="test-password", first_name="Clone")
    user.student_id = allocate_student_id("Clone")
    from django.contrib.auth.models import Group

    user.groups.add(Group.objects.get(name="Student"))
    credential, _ = SimulatorCredential.objects.get_or_create(user=user)
    credential.issue()
    return user


def _attach(source, name, row):
    UcrDocumentAttachment.objects.create(
        ucr=source,
        row_index=row,
        file=SimpleUploadedFile(name, b"fictional attachment bytes"),
        original_name=name,
    )


@pytest.mark.django_db
def test_clone_copies_attachments_after_draft_is_saved(client, simulator_student):
    from django.contrib.auth.models import Group

    source = UcrDeclaration.objects.create(
        owner=simulator_student, ucr_no="KGHTESTUCRCLONE01", status="submitted",
        regime="10", declarant_code="CLN001",
    )
    _attach(source, "packing-list.pdf", 1)
    _attach(source, "invoice.pdf", 2)

    client.force_login(simulator_student)
    session = client.session
    session["simulator_user_id"] = str(simulator_student.pk)
    session.save()

    response = client.post(reverse("ucr-clone", args=[source.pk]))
    assert response.status_code == 302
    assert response.url.startswith(reverse("single-window-create-ucr"))

    draft = UcrDeclaration.objects.get(derivation="clone", source_ucr=source)
    assert draft.status == UcrDeclaration.Status.DRAFT
    assert draft.temp_no.startswith(UcrDeclaration.TEMP_PREFIX)
    copied = list(draft.attachments.order_by("row_index"))
    assert [a.original_name for a in copied] == ["packing-list.pdf", "invoice.pdf"]
    assert all(a.ucr_id == draft.pk for a in copied)
