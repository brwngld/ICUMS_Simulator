import math
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView as AuthLoginView
from django.db import transaction
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse
from django.utils import dateformat, timezone
from django.views.decorators.http import require_POST

from core import throttle
from core.admin_dashboard import render_student_page
from reports.models import CompletionRecord
from audit.models import AuditEvent
from .forms import (
    CredentialRenewalForm,
    PasswordChangeForm as ProfilePasswordChangeForm,
    PreferencesForm,
    ProfileForm,
    StudentRegistrationForm,
    UnfoldLoginForm,
)
from .models import SimulatorCredential, UserPreference, allocate_student_id


@transaction.atomic
def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    address = throttle.client_address(request)
    blocked = request.method == "POST" and throttle.exhausted(
        "register:address", address, throttle.REGISTRATION_ADDRESS_LIMIT, throttle.REGISTRATION_WINDOW_SECONDS
    )
    if blocked:
        messages.error(request, "Too many sign-up attempts from this network. Please try again later.")
    else:
        throttle.record("register:address", address, throttle.REGISTRATION_WINDOW_SECONDS)
    form = StudentRegistrationForm(request.POST if request.method == "POST" and not blocked else None)
    if request.method == "POST" and not blocked and form.is_valid():
        user = form.save(commit=False)
        user.student_id = allocate_student_id(user.first_name)
        user.username = user.student_id
        user.save()
        student_group, _ = Group.objects.get_or_create(name="Student")
        user.groups.add(student_group)
        login(request, user)
        messages.success(request, f"Registration complete. Your Student ID is {user.student_id}.")
        return redirect("dashboard")
    # The registration page renders through the Unfold design system and
    # needs the admin site's presentation context, exactly like the login
    # page. Registration behaviour is untouched.
    from django.contrib import admin as admin_site

    context = {"form": form}
    context.update(admin_site.site.each_context(request))
    return render(request, "registration/register.html", context)



class LoginView(AuthLoginView):
    """Django's login view with one adjustment: after signing in,
    administrators land on the Unfold admin dashboard while students and
    tutors land on the learning portal. An explicit ?next= destination
    still wins, exactly as in Django's own view.

    The login page renders through the Unfold design system, so it needs
    the admin site's presentation context (palette variables, fonts
    wiring, theme) — the same context render_student_page supplies for
    portal pages. Authentication behaviour is untouched.
    """

    form_class = UnfoldLoginForm

    def post(self, request, *args, **kwargs):
        """Refuse sign-ins from an address or for an account with too many
        recent failures (audit SEC-08); the form is re-rendered with the
        notice instead of attempting authentication."""
        username = request.POST.get("username", "").strip().lower()
        address = throttle.client_address(request)
        if throttle.exhausted("login:account", username, throttle.LOGIN_ACCOUNT_LIMIT, throttle.LOGIN_WINDOW_SECONDS) or throttle.exhausted(
            "login:address", address, throttle.LOGIN_ADDRESS_LIMIT, throttle.LOGIN_WINDOW_SECONDS
        ):
            messages.error(request, "Too many failed sign-in attempts. Please wait a few minutes and try again.")
            return self.get(request, *args, **kwargs)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        throttle.clear("login:account", self.request.POST.get("username", "").strip().lower())
        return super().form_valid(form)

    def form_invalid(self, form):
        username = self.request.POST.get("username", "").strip().lower()
        throttle.record("login:account", username, throttle.LOGIN_WINDOW_SECONDS)
        throttle.record("login:address", throttle.client_address(self.request), throttle.LOGIN_WINDOW_SECONDS)
        return super().form_invalid(form)

    def get_success_url(self):
        url = self.get_redirect_url()
        if url:
            return url
        if self.request.user.is_staff:
            return reverse("admin:index")
        return resolve_url(settings.LOGIN_REDIRECT_URL)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.contrib import admin as admin_site

        context.update(admin_site.site.each_context(self.request))
        return context


@login_required
def account_settings(request):
    """The learner's Settings page: profile, security, simulator access,
    certificate and the account controls around them.

    Renders through the shared shell, so students, tutors and administrators
    all reach it from the same account menu. Several forms share the page:
    the profile form, the change-password form the dialog posts, and the
    sign-out-everywhere action in the danger zone.
    """
    password_form = None
    preferences_form = None
    stored_preferences = UserPreference.objects.filter(user=request.user).first()
    if request.method == "POST" and request.POST.get("action") == "change-password":
        form = ProfileForm(instance=request.user)
        password_form = ProfilePasswordChangeForm(request.user, request.POST)
        if password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Your password was changed.")
            return redirect("account-settings")
        # Invalid: the page re-renders with the dialog already open.
    elif request.method == "POST" and request.POST.get("action") == "save-preferences":
        form = ProfileForm(instance=request.user)
        preferences_form = PreferencesForm(request.POST, instance=stored_preferences)
        if preferences_form.is_valid():
            preferences = preferences_form.save(commit=False)
            preferences.user = request.user
            preferences.save()
            messages.success(request, "Your preferences were saved.")
            return redirect("account-settings")
    elif request.method == "POST" and request.POST.get("action") == "sign-out-everywhere":
        ended = _sign_out_other_sessions(request)
        messages.success(request, f"Signed out of {ended} other session{'s'[:ended != 1]}." if ended else "No other sessions were signed in.")
        return redirect("account-settings")
    elif request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your account details were saved.")
            return redirect("account-settings")
    else:
        form = ProfileForm(instance=request.user)
    password_form = password_form or ProfilePasswordChangeForm(request.user)
    preferences_form = preferences_form or PreferencesForm(instance=stored_preferences)
    groups = list(request.user.groups.values_list("name", flat=True))
    credential = SimulatorCredential.objects.filter(user=request.user).first()
    issued_by = (
        AuditEvent.objects.filter(action_code="simulator.credential_issued", target_id=str(request.user.pk))
        .select_related("actor")
        .order_by("-created_at")
        .values_list("actor__first_name", "actor__last_name")
        .first()
    )
    completion = (
        CompletionRecord.objects.filter(enrolment__student=request.user)
        .select_related("certificate")
        .order_by("-created_at")
        .first()
    )
    return render_student_page(
        request,
        "accounts/settings.html",
        {
            "form": form,
            "password_form": password_form,
            "password_errors": request.method == "POST" and request.POST.get("action") == "change-password" and bool(password_form.errors),
            "preferences_form": preferences_form,
            "groups": groups,
            "credential": credential,
            "issued_by": " ".join(name for name in issued_by if name) if issued_by else "",
            "completion": completion,
            "unread_notifications": request.user.notifications.filter(read_at__isnull=True).count(),
        },
    )


@login_required
def account_credential(request):
    """The learner's credential-management page: status, sign-in details,
    and the renewal request that goes to the instructor.

    A freshly issued password is displayed on this very load — the one time —
    and revealed_at closes it forever after; only its state is shown otherwise.
    """
    credential = SimulatorCredential.objects.filter(user=request.user).first()
    renewal_form = CredentialRenewalForm()
    reveal_password = None
    if credential and credential.password_state == "awaiting_reveal" and credential.issued_at:
        reveal_password = credential.recompute_password()
        credential.mark_revealed()
    if request.method == "POST" and credential:
        action = request.POST.get("action")
        if action == "request-renewal":
            if credential.reset_requested_at:
                messages.info(request, "Your renewal request is already with your instructor.")
                return redirect("account-credential")
            if not _renewal_window_open(credential):
                messages.warning(request, "Renewal requests open 7 days before your credential expires.")
                return redirect("account-credential")
            renewal_form = CredentialRenewalForm(request.POST)
            if renewal_form.is_valid():
                credential.reset_requested_at = timezone.now()
                credential.reset_reason = renewal_form.cleaned_data["reason"]
                credential.reset_note = renewal_form.cleaned_data["note"]
                credential.save(update_fields=("reset_requested_at", "reset_reason", "reset_note"))
                messages.success(request, "Your renewal request was sent to your instructor.")
                return redirect("account-credential")
        elif action == "cancel-renewal":
            credential.reset_requested_at = None
            credential.reset_reason = ""
            credential.reset_note = ""
            credential.save(update_fields=("reset_requested_at", "reset_reason", "reset_note"))
            messages.info(request, "Your renewal request was cancelled.")
            return redirect("account-credential")

    now = timezone.now()
    state = "none"
    days_left = 0
    progress = 100
    opens_on = None
    if credential and credential.issued_at and credential.expires_at:
        total = (credential.expires_at - credential.issued_at).total_seconds()
        elapsed = min(max((now - credential.issued_at).total_seconds(), 0.0), total)
        progress = round(elapsed / total * 100) if total > 0 else 100
        remaining = (credential.expires_at - now).total_seconds()
        days_left = max(0, math.ceil(remaining / 86400))
        if remaining <= 0:
            state = "expired"
        elif remaining <= 7 * 86400:
            state = "expiring"
        else:
            state = "active"
        opens_on = dateformat.format(credential.expires_at - timedelta(days=7), "j F Y")
    return render_student_page(
        request,
        "accounts/credential.html",
        {
            "credential": credential,
            "reveal_password": reveal_password,
            "state": state,
            "days_left": days_left,
            "progress": progress,
            "renewal_form": renewal_form,
            "renewal_open": bool(credential and not credential.reset_requested_at and state in ("expired", "expiring")),
            "opens_on": opens_on,
            "unread_notifications": request.user.notifications.filter(read_at__isnull=True).count(),
        },
    )


def _renewal_window_open(credential):
    """Renewal requests open in the last week of the credential, and after expiry."""
    if not credential.expires_at:
        return False
    return (credential.expires_at - timezone.now()).total_seconds() <= 7 * 86400


def _sign_out_other_sessions(request):
    """End every other signed-in session this account holds; keep this one."""
    from django.contrib.sessions.models import Session

    current_key = request.session.session_key
    ended = 0
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if session.session_key == current_key:
            continue
        if str(session.get_decoded().get("_auth_user_id")) == str(request.user.pk):
            session.delete()
            ended += 1
    return ended


@login_required
def notifications(request):
    """The notification centre: most recent first, unread rows highlighted."""
    items = list(request.user.notifications.all()[:50])
    return render_student_page(
        request,
        "accounts/notifications.html",
        {
            "notifications": items,
            "unread_notifications": sum(1 for item in items if not item.is_read),
        },
    )


@login_required
@require_POST
def notifications_mark_read(request):
    """Mark every notice, or one named notice, as read and return to the centre."""
    from django.core.exceptions import ValidationError

    value = str(request.POST.get("notification", "")).strip()
    unread = request.user.notifications.filter(read_at__isnull=True)
    marked = None
    if value:
        try:
            marked = unread.filter(pk=value).update(read_at=timezone.now())
        except (ValueError, ValidationError):
            marked = 0
    if marked is None:
        count = unread.update(read_at=timezone.now())
        messages.success(request, f"{count} notification{'s'[:count != 1]} marked as read." if count else "You're all caught up.")
    elif marked:
        messages.success(request, "Notification marked as read.")
    else:
        messages.info(request, "That notification was already read.")
    return redirect("account-notifications")
