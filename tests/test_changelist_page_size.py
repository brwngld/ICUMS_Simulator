"""Configurable page sizes on Unfold changelists (10/20/50/100/200)."""
import pytest
from django.urls import reverse

from accounts.models import User
from audit.models import AuditEvent


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(username="page-admin", email="page-admin@example.test", password="test-password")


@pytest.fixture
def audit_rows(db, admin_user):
    events = [
        AuditEvent(actor=admin_user, action_code="test.page", target_type="test", target_id=str(i), summary=f"event {i}")
        for i in range(35)
    ]
    return AuditEvent.objects.bulk_create(events)


CHANGELIST = reverse("admin:audit_auditevent_changelist")


def _rows(response) -> int:
    """Rows actually displayed on the page, from the changelist itself."""
    return len(response.context["cl"].result_list)


def _selected_size(html: str):
    import re

    match = re.search(r'<option value="(\d+)" selected', html)
    return int(match.group(1)) if match else None


@pytest.mark.django_db
def test_page_size_selector_renders(client, admin_user, audit_rows):
    client.force_login(admin_user)
    response = client.get(CHANGELIST)
    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="page-size"' in html
    for option in (10, 20, 50, 100, 200):
        assert f'<option value="{option}"' in html
    assert _selected_size(html) == 100  # ModelAdmin default


@pytest.mark.django_db
@pytest.mark.parametrize("size", [10, 20, 50, 100, 200])
def test_every_page_size_option(client, admin_user, audit_rows, size):
    client.force_login(admin_user)
    response = client.get(CHANGELIST, {"page_size": str(size)})
    assert response.status_code == 200
    html = response.content.decode()
    assert _selected_size(html) == size
    assert _rows(response) == min(size, AuditEvent.objects.count())


@pytest.mark.django_db
def test_invalid_page_size_falls_back_to_default(client, admin_user, audit_rows):
    client.force_login(admin_user)
    for bad in ("7", "abc", "-10", "1000"):
        response = client.get(CHANGELIST, {"page_size": bad})
        assert response.status_code == 200
        assert _selected_size(response.content.decode()) == 100


@pytest.mark.django_db
def test_page_navigation_preserves_page_size_and_search(client, admin_user, audit_rows):
    client.force_login(admin_user)
    response = client.get(CHANGELIST, {"page_size": "10", "q": "event 3"})
    assert response.status_code == 200
    html = response.content.decode()
    # Pagination links built from the changelist params keep the size and search.
    assert "page_size=10" in html
    assert "q=event" in html


@pytest.mark.django_db
def test_size_change_returns_to_page_one(client, admin_user, audit_rows):
    client.force_login(admin_user)
    response = client.get(CHANGELIST, {"page_size": "10", "p": "2"})
    assert response.status_code == 200
    html = response.content.decode()
    # The selector form always submits page 1.
    assert 'name="p" value="1"' in html
    assert _rows(response) == 10


@pytest.mark.django_db
def test_empty_results_page(client, admin_user):
    client.force_login(admin_user)
    response = client.get(CHANGELIST, {"page_size": "10", "q": "nothing-matches-this"})
    assert response.status_code == 200
    assert "0 results" in response.content.decode()


@pytest.mark.django_db
def test_final_page_shows_remaining_rows(client, admin_user, audit_rows):
    client.force_login(admin_user)
    response = client.get(CHANGELIST, {"page_size": "10", "p": "4"})
    assert response.status_code == 200
    total = AuditEvent.objects.count()
    full_pages, remainder = divmod(total, 10)
    expected = remainder or 10
    assert _rows(response) == expected  # final page shows what is left


@pytest.mark.django_db
def test_page_size_not_exposed_to_anonymous(client, audit_rows):
    response = client.get(CHANGELIST, {"page_size": "10"})
    assert response.status_code == 302  # login redirect; no data leaks
