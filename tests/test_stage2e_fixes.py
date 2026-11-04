"""Stage 2E — regression coverage for the four verified browser defects.

The multipart tests reproduce the exact request shape the browser sends
(``multipart/form-data`` with the payload and any idempotency key as form
fields); the wiring tests pin the client-side corrections to the studio and
workspace scripts, whose behavioural proof is the real-browser walk of the
same stage.
"""
import json
import re
import uuid

import pytest
from django.contrib.staticfiles import finders
from django.test import Client, override_settings
from django.urls import reverse

from demonstration_world import draft_world
from hybrid.models import DemonstrationEvent, DemonstrationSession
from scenarios.models import UcrDeclaration

enabled = override_settings(DEMONSTRATION_RECORDING_ENABLED=True)


def save_body(**overrides):
    payload = {
        "regime": "TN",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "Fix Provider",
            "country": "GH", "address": "1 Provider Road", "contact": "Provider Contact",
            "phone": "+233200000003", "email": "provider@example.test", "email_2": "",
        },
        "exporter": {
            "name": "Fix Exporter", "country": "GH", "address": "1 Export Road",
            "phone": "+233200000001", "contact": "Export Contact",
            "contact_no": "+233200000002", "designation": "Manager",
        },
        "importer": {
            "name": "Fix Importer", "country": "CN", "address": "1 Import Road",
            "phone": "+861000000001", "contact": "Import Contact",
            "contact_no": "+861000000003", "designation": "Manager",
        },
        "consignment": {
            "goods": "Fix goods", "origin": "GH", "destination": "CN", "mode": "10, Sea Transport",
        },
    }
    payload.update(overrides)
    return payload


def bound_client(username_seed):
    """A fresh instructor with a draft lesson and a live recording binding.

    ``draft_world`` (no pre-made session) is required: ``recording()`` worlds
    already hold the instructor's one live session, so the browser's start is
    refused with ``session_active`` — the guard working as designed.
    """
    world = draft_world(username_seed)
    client = Client()
    client.force_login(world["instructor"])
    started = client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk]))
    assert started.status_code == 200, started.content
    session = DemonstrationSession.objects.get(pk=started.json()["session"]["id"])
    return world, client, session


# --- Fix 1: the browser-style multipart save ---------------------------------


@pytest.mark.django_db
@enabled
def test_a_browser_style_multipart_demonstration_save_succeeds(db):
    """The studio frame posts FormData: multipart, payload as a form field, no
    files. This exact shape 500ed before the fix; it must save a DEMOUCR draft
    and record its event."""
    world, client, session = bound_client("fix-multipart")
    key = str(uuid.uuid4())

    response = client.post(
        reverse("ucr-save"),
        {"payload": json.dumps(save_body()), "idempotency_key": key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["demonstration"] is True
    record = UcrDeclaration.all_objects.get(pk=data["id"])
    assert record.demonstration_session_id == session.pk
    assert record.temp_no.startswith("DEMOUCR")
    event = DemonstrationEvent.objects.get(session_id=session.pk, sequence=1)
    assert event.event_type == "record_created"
    assert event.record_id == record.pk
    assert str(event.idempotency_key) == key


@pytest.mark.django_db
@enabled
def test_multipart_replay_with_the_same_key_stays_idempotent(db):
    world, client, session = bound_client("fix-multipart-replay")
    key = str(uuid.uuid4())

    first = client.post(reverse("ucr-save"), {"payload": json.dumps(save_body()), "idempotency_key": key})
    second = client.post(reverse("ucr-save"), {"payload": json.dumps(save_body()), "idempotency_key": key})

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert UcrDeclaration.all_objects.filter(demonstration_session=session).count() == 1
    assert DemonstrationEvent.objects.filter(session_id=session.pk).count() == 1


@pytest.mark.django_db
@enabled
def test_multipart_attachment_refusal_and_isolation_are_untouched(db):
    """The fix narrows nothing: files are still refused, and the draft stays
    scoped to the session."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    world, client, session = bound_client("fix-multipart-files")

    refused = client.post(
        reverse("ucr-save"),
        {
            "payload": json.dumps(save_body(documents=[{"code": "DOC1", "name": "E", "reference": "R"}])),
            "file_0": SimpleUploadedFile("e.pdf", b"%PDF-1.4 x"),
        },
    )
    assert refused.status_code == 400
    assert refused.json()["code"] == "attachment_denied"
    assert UcrDeclaration.all_objects.filter(demonstration_session=session).count() == 0


# --- Fixes 2-4: client wiring pinned where a server test can see it ----------


@pytest.mark.django_db
@enabled
def test_the_studio_live_branch_refreshes_controls_and_retains_the_stopped_session(db):
    from pathlib import Path

    from django.conf import settings

    world, client, session = bound_client("fix-studio-wiring")

    html = client.get(
        reverse("hybrid-lesson-demonstration-studio", args=[world["lesson"].pk])
    ).content.decode()

    # Fix 2: every lifecycle response refreshes the button states.
    assert "renderControls();" in html
    # Fix 3: the stopped session's id is retained in page state and Review
    # fetches proposals for it after the binding is gone.
    assert "retainedSessionId" in html
    assert "loadProposals()" in html

    # The identifier is page state only — never persisted to browser storage.
    # (Scoped to the studio's own script: the site chrome's sidebar uses
    # localStorage for itself and is none of this feature's business.)
    template = Path(settings.BASE_DIR) / "templates" / "hybrid" / "demonstration_studio.html"
    scripts = re.findall(r"<script>(.*?)</script>", template.read_text(encoding="utf-8"), re.S)
    studio_script = next(script for script in scripts if "retainedSessionId" in script)
    assert "sessionStorage" not in studio_script and "localStorage" not in studio_script


@pytest.mark.django_db
def test_the_workspace_refreshes_its_csrf_token_when_the_frame_loads(db):
    script = finders.find("js/hybrid-workspace.js")
    assert script, "hybrid-workspace.js must be collectable"
    with open(script, encoding="utf-8") as handle:
        source = handle.read()

    # Fix 4: the frame's load event lifts a fresh token into #hyb-csrf, so
    # acknowledge/check/advance survive the simulator login's token rotation.
    assert 'addEventListener("load", refreshCsrfToken)' in source
    assert "csrfmiddlewaretoken" in source
