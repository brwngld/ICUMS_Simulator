"""Fast, isolated settings for automated tests."""

from .base import *  # noqa: F403

SECRET_KEY = "test-only-secret-key"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# The auth rate limiter counts failures in the default cache; a no-op cache
# keeps suites that sign in repeatedly unaffected. The limiter's own tests opt
# into a real cache with override_settings.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
