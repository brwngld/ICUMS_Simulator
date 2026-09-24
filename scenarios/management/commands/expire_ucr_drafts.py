"""Delete TEMPUCR drafts that were never submitted within the retention window."""

from django.core.management.base import BaseCommand

from scenarios.models import purge_expired_ucr_drafts


class Command(BaseCommand):
    help = "Deletes UCR drafts (TEMPUCR records) older than the retention window that were never submitted."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7, help="Draft retention window in days (default: 7).")

    def handle(self, *args, **options):
        deleted = purge_expired_ucr_drafts(max_age_days=options["days"])
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired UCR draft(s)."))
