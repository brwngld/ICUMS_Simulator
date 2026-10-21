"""The account menu's Settings page and notification centre.

Every signed-in role reaches both from the same account menu, so these tests
use a plain student plus one instructor check: the menu links render for
either, the settings form saves the learner's own details, and the
notification centre lists, highlights and clears its rows.
"""

from datetime import timedelta
from django.test import Client
from django.urls import reverse
from django.utils import timezone

import pytest

from accounts.models import Notification, User, UserPreference
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion


@pytest.fixture
def student(db):
    user = User.objects.create_user(
        username="settings-student", email="settings-student@example.test",
        password="test-password", first_name="Set", last_name="Thing",
    )
    disclaimer = DisclaimerVersion.objects.create(version=1, title="Training notice", body="Not official ICUMS.", is_current=True)
    DisclaimerAcceptance.objects.create(user=user, disclaimer=disclaimer)
    return user


def _login(client, user):
    client.force_login(user)


def test_the_account_menu_offers_settings_and_notifications(client, student):
    Notification.objects.create(recipient=student, title="Simulator access granted")
    _login(client, student)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    html = response.content.decode()
    assert reverse("account-settings") in html
    assert reverse("account-notifications") in html
    # The unread badge shows the count next to the Notifications entry.
    assert ">1<" in html


def test_the_badge_disappears_when_everything_is_read(client, student):
    _login(client, student)
    html = client.get(reverse("dashboard")).content.decode()
    assert reverse("account-notifications") in html
    assert "bg-primary-600 rounded-full" not in html


def test_settings_shows_details_and_saves_changes(client, student):
    student.student_id = "ST000001"
    student.save()
    _login(client, student)

    html = client.get(reverse("account-settings")).content.decode()
    assert 'value="Set"' in html
    assert "settings-student@example.test" in html
    assert "ST000001" in html

    response = client.post(
        reverse("account-settings"),
        {
            "first_name": "Setti", "last_name": "Ng", "email": "setti@example.test",
            "phone": "+233 20 000 0000", "organisation": "Ashanti Clearing Agency",
            "certificate_name": "Setti Ng", "country": "GH",
        },
    )
    assert response.status_code == 302
    student.refresh_from_db()
    assert (student.first_name, student.last_name, student.email) == ("Setti", "Ng", "setti@example.test")
    assert student.phone == "+233 20 000 0000"
    assert student.organisation == "Ashanti Clearing Agency"
    assert student.certificate_name == "Setti Ng"
    assert student.country == "GH"


def test_settings_refuses_an_email_another_account_holds(client, student, db):
    User.objects.create_user(username="other", email="taken@example.test", password="x")
    response = client.post(
        reverse("account-settings"),
        {"first_name": "Set", "last_name": "Thing", "email": "taken@example.test"},
    )
    _login(client, student)
    response = client.post(
        reverse("account-settings"),
        {"first_name": "Set", "last_name": "Thing", "email": "taken@example.test"},
    )
    assert response.status_code == 200
    assert "already exists" in response.content.decode()


def test_notifications_list_newest_first_and_mark_the_unread(client, student):
    first = Notification.objects.create(recipient=student, title="Oldest notice", body="Earlier.")
    newest = Notification.objects.create(recipient=student, title="Newest notice", body="Later.", url="/theory/")
    # Two rows can share one microsecond; make the ordering unambiguous.
    Notification.objects.filter(pk=first.pk).update(created_at=timezone.now() - timedelta(seconds=5))
    _login(client, student)

    html = client.get(reverse("account-notifications")).content.decode()
    assert html.index("Newest notice") < html.index("Oldest notice")
    assert html.count("is-unread") == 2
    assert "/theory/" in html
    assert "Mark all as read" in html

    client.post(reverse("account-notifications-read"))
    newest.refresh_from_db()
    first.refresh_from_db()
    assert newest.is_read and first.is_read
    assert client.get(reverse("account-notifications")).content.decode().count("is-unread") == 0


def test_one_notice_can_be_marked_read_alone(client, student):
    kept = Notification.objects.create(recipient=student, title="Keep unread")
    read = Notification.objects.create(recipient=student, title="Read me")
    _login(client, student)
    client.post(reverse("account-notifications-read"), {"notification": str(read.pk)})
    kept.refresh_from_db()
    read.refresh_from_db()
    assert kept.read_at is None
    assert read.is_read


def test_an_empty_notification_centre_has_a_styled_placeholder(client, student):
    _login(client, student)
    html = client.get(reverse("account-notifications")).content.decode()
    assert "No notifications yet" in html


@pytest.mark.django_db
def test_settings_and_notifications_require_signing_in(client, db):
    assert client.get(reverse("account-settings")).status_code == 302
    assert client.get(reverse("account-notifications")).status_code == 302


@pytest.mark.django_db
def test_an_instructor_sees_the_same_menu_entries(client, db):
    from django.contrib.auth.models import Group

    instructor = User.objects.create_user(username="settings-instructor", email="si@example.test", password="x")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    client.force_login(instructor)
    html = client.get(reverse("dashboard")).content.decode()
    assert reverse("account-settings") in html
    assert reverse("account-notifications") in html


def test_the_settings_page_carries_the_change_password_dialog(client, student):
    _login(client, student)
    html = client.get(reverse("account-settings")).content.decode()
    assert 'id="password-change-dialog"' in html
    assert 'name="old_password"' in html
    assert 'name="new_password1"' in html
    assert 'name="new_password2"' in html
    # The form posts back to the Settings page, not a separate route.
    assert f'action="{reverse("account-settings")}"' in html


def test_the_account_menu_lands_on_the_settings_dialog(client, student):
    _login(client, student)
    html = client.get(reverse("dashboard")).content.decode()
    # The menu's Change password entry opens the Settings dialog via the hash.
    assert f'{reverse("account-settings")}#change-password' in html


def test_a_failed_change_reopens_the_dialog_with_the_error(client, student):
    _login(client, student)
    response = client.post(
        reverse("account-settings"),
        {"action": "change-password", "old_password": "wrong-old", "new_password1": "n3w-Secret-9x", "new_password2": "n3w-Secret-9x"},
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "old password" in html.lower()
    assert 'data-open="true"' in html


def test_a_successful_change_stays_signed_in_and_needs_no_page(client, student):
    _login(client, student)
    response = client.post(
        reverse("account-settings"),
        {"action": "change-password", "old_password": "test-password", "new_password1": "n3w-Secret-9x", "new_password2": "n3w-Secret-9x"},
    )
    assert response.status_code == 302
    assert response.url == reverse("account-settings")
    student.refresh_from_db()
    assert student.check_password("n3w-Secret-9x")
    # The current session survives the change.
    assert client.get(reverse("account-settings")).status_code == 200


def test_the_settings_page_has_the_redesigned_sections(client, student):
    _login(client, student)
    html = client.get(reverse("account-settings")).content.decode()
    for section in ("profile", "security", "simulator", "certificate", "notifications", "preferences", "privacy", "danger"):
        assert f'id="{section}"' in html
    # Certificate is a nav title of its own.
    assert ">Certificate</a>" in html
    # A learner without a completion record sees the honest placeholder.
    assert "Not yet available" in html


@pytest.mark.django_db
def test_sign_out_everywhere_keeps_this_session_only(client, db):
    from django.contrib.sessions.models import Session

    learner = User.objects.create_user(username="multi-session", email="multi@example.test", password="test-password")
    disclaimer = DisclaimerVersion.objects.create(version=1, title="Training notice", body="Not official ICUMS.", is_current=True)
    DisclaimerAcceptance.objects.create(user=learner, disclaimer=disclaimer)

    staying = Client()
    staying.force_login(learner)
    leaving = Client()
    leaving.force_login(learner)
    assert Session.objects.count() == 2

    response = staying.post(reverse("account-settings"), {"action": "sign-out-everywhere"})
    assert response.status_code == 302
    assert Session.objects.count() == 1
    assert staying.get(reverse("account-settings")).status_code == 200
    assert leaving.get(reverse("dashboard")).status_code == 302


def test_preferences_save_and_reload_their_selection(client, student):
    from accounts.models import UserPreference

    _login(client, student)
    response = client.post(
        reverse("account-settings"),
        {"action": "save-preferences", "language": "fr", "timezone": "UTC", "date_format": "m/d/Y", "expiry_reminder_days": "3"},
    )
    assert response.status_code == 302
    preferences = UserPreference.objects.get(user=student)
    assert (preferences.language, preferences.timezone, preferences.date_format, preferences.expiry_reminder_days) == ("fr", "UTC", "m/d/Y", 3)

    html = client.get(reverse("account-settings")).content.decode()
    assert 'value="fr" selected' in html
    assert 'value="UTC" selected' in html
    assert 'value="3" selected' in html


def test_preferences_offer_every_choice_and_default_to_the_mockups(client, student):
    _login(client, student)
    html = client.get(reverse("account-settings")).content.decode()
    # The apostrophe in "Don't" is HTML-escaped in the rendered options.
    for option in ("Français", "Africa/Lagos (GMT+1)", "09/25/2026", "Don&#x27;t remind me"):
        assert option in html
    # A learner who hasn't chosen anything sees the defaults, and no row
    # exists until the first save.
    assert 'value="en" selected' in html
    assert 'value="7" selected' in html
    assert not UserPreference.objects.filter(user=student).exists()


def test_expiry_reminder_can_be_switched_off(client, student):
    from accounts.models import UserPreference

    _login(client, student)
    client.post(
        reverse("account-settings"),
        {"action": "save-preferences", "language": "en", "timezone": "Africa/Accra", "date_format": "d M Y", "expiry_reminder_days": "0"},
    )
    assert UserPreference.objects.get(user=student).expiry_reminder_days == 0
