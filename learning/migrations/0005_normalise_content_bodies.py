"""Rewrite stored lesson bodies once, so legacy plain text and editor HTML share one shape.

``ContentBlock.save`` already normalises every new write; this migration applies the same
conversion to the rows that predate it. ``linebreaks`` semantics are preserved, so a lesson
that was plain text before still renders as the same paragraphs afterwards.
"""

from django.db import migrations

from learning.rich_text import to_safe_html


def normalise_bodies(apps, schema_editor):
    ContentBlock = apps.get_model("learning", "ContentBlock")
    for block in ContentBlock.objects.iterator(chunk_size=200):
        html = to_safe_html(block.body)
        if html != block.body:
            ContentBlock.objects.filter(pk=block.pk).update(body=html)


def keep_bodies_unchanged(apps, schema_editor):
    """Reversing cannot recover the original text, so the data is left alone."""


class Migration(migrations.Migration):
    dependencies = [("learning", "0004_module_difficulty")]

    operations = [migrations.RunPython(normalise_bodies, keep_bodies_unchanged)]
