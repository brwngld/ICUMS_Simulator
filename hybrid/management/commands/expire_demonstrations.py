"""Close abandoned recordings, then delete sealed demonstrations past their deadline.

One command, two sweeps, in that order — the first is what makes a lapsed
recording eligible for the second. Ordinary ``expire_ucr_drafts`` never reaches a
demonstration record, because the ordinary manager hides those rows by
construction, so this is the only cleanup demonstration data ever gets.

The inactivity sweep seals any recording or pause whose instructor stopped touching
it: the session becomes stopped, its timeline and records stay reviewable, and the
one live-session slot it was holding is released. A browser left open on the Studio
does not extend that deadline, because the deadline is measured from deliberate
activity only — which is why the sweep has to run at all, and why it must run more
often than the window it enforces.

The expiry sweep then deletes the sessions whose ``retention_expires_at`` has
arrived, stopped or discarded alike. That deadline was stamped at the moment the
session closed, so the command takes no window of its own: changing
``RETENTION_DAYS`` affects future sessions only, and a session already sealed keeps
the deadline it was given.

Both sweeps are idempotent, and neither is assumed. Nothing in the application runs
them on a timer, exactly as ``expire_ucr_drafts`` is not self-scheduling;
``docs/demonstration-recording-operations.md`` carries the cron entry to add when the
recorder goes live. Until something does schedule this, an abandoned recording holds
its instructor's slot until they start a new one — which seals it — and a stopped
session keeps its records until an instructor discards it.
"""
from django.core.management.base import BaseCommand

from hybrid import demonstrations


class Command(BaseCommand):
    help = (
        "Seals demonstration recordings that went inactive, then deletes stopped and "
        "discarded demonstration sessions whose retention deadline has passed, together "
        "with their events and demonstration records."
    )

    def handle(self, *args, **options):
        sealed = demonstrations.seal_abandoned_sessions()
        removed = demonstrations.expire_demonstrations()
        self.stdout.write(self.style.SUCCESS(f"Sealed {sealed} abandoned, removed {removed} expired."))
