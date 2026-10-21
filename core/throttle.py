"""Fixed-window rate limiting for the public authentication endpoints.

Failed sign-ins and sign-ups are counted in the default cache, keyed by scope
and by the client address the nearest trusted proxy reported: the project's
nginx appends the real client to ``X-Forwarded-For``, so its last entry is the
one to trust, and a direct connection falls back to ``REMOTE_ADDR``. Limits
are counted per account as well as per address, so rotating addresses does not
reset an account's counter (audit SEC-08). Successful authentication clears
the account's counter, so a learner who mistypes once is never locked out.

The default LocMemCache is per-process, which matches this project's single
Waitress process behind nginx; pointing ``CACHES`` at a shared backend
strengthens it further. Automated tests run against ``DummyCache`` (see
``config/settings/test.py``) so suites that sign in repeatedly are unaffected.
"""

from django.core.cache import cache

#: Main sign-in: failures per account and per address within the window.
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_ACCOUNT_LIMIT = 5
LOGIN_ADDRESS_LIMIT = 30

#: Public registration: attempts per address (valid or not) within the window.
REGISTRATION_WINDOW_SECONDS = 60 * 60
REGISTRATION_ADDRESS_LIMIT = 10

#: Simulator credential sign-in: failures per Student ID and per address.
SIMULATOR_WINDOW_SECONDS = 15 * 60
SIMULATOR_ID_LIMIT = 5
SIMULATOR_ADDRESS_LIMIT = 30


def client_address(request):
    """The client address to rate-limit on, as reported by our own proxy."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    return hops[-1] if hops else request.META.get("REMOTE_ADDR") or "unknown"


def _key(scope, identifier):
    return f"throttle:{scope}:{identifier}"


def exhausted(scope, identifier, limit, window_seconds):
    """True when the failure counter for this scope has reached its limit."""
    count = cache.get(_key(scope, identifier))
    return count is not None and count >= limit


def record(scope, identifier, window_seconds):
    """Count one failure; the counter expires with the window."""
    key = _key(scope, identifier)
    try:
        return cache.incr(key)
    except ValueError:
        cache.add(key, 1, timeout=window_seconds)
        return 1


def clear(scope, identifier):
    """Forget this scope's counter, e.g. after a successful sign-in."""
    cache.delete(_key(scope, identifier))
