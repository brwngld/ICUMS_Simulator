"""Practical lessons are training, not examinations: allow repeat attempts.

The old table-wide unique(enrolment, lesson) made a completed attempt a
one-time ticket — a learner who finished a practical lesson could never
practise it again without a new enrolment. The constraint becomes "one OPEN
attempt per (enrolment, lesson)": completed attempts stay exactly as they are
(never reset, never overwritten, progression reads any of them), and at most
one fresh attempt can exist at a time. Every existing row satisfies both
shapes, so this is a no-op on live data.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hybrid", "0012_alter_demonstrationsession_retention_expires_at"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="lessonattempt",
            name="unique_hybrid_attempt_per_lesson",
        ),
        migrations.AddConstraint(
            model_name="lessonattempt",
            constraint=models.UniqueConstraint(
                condition=models.Q(completed_at__isnull=True),
                fields=("enrolment", "lesson"),
                name="unique_hybrid_open_attempt_per_lesson",
            ),
        ),
    ]
