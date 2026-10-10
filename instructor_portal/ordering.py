"""Deterministic reordering for draft-course modules and lessons.

Positions are compacted to 1..N on every move, so no duplicate or missing
orders can accumulate. Ordering ties break exactly as the roadmap sees them
(``order`` then ``title``, matching the models' Meta ordering), so the
student-facing sequence always follows the saved order.
"""

from django.db import transaction

from learning.models import Lesson

DIRECTIONS = ("up", "down")


def _move(queryset, target, direction):
    """Swap `target` with its neighbour in `queryset` order and renumber
    1..N. Returns True when the order changed."""
    if direction not in DIRECTIONS:
        raise ValueError(f"Unknown direction: {direction!r}")
    items = list(queryset)
    index = next((i for i, item in enumerate(items) if item.pk == target.pk), None)
    if index is None:
        return False
    neighbour = index - 1 if direction == "up" else index + 1
    if neighbour < 0 or neighbour >= len(items):
        return False
    items[index], items[neighbour] = items[neighbour], items[index]
    with transaction.atomic():
        for position, item in enumerate(items, start=1):
            if item.order != position:
                item.order = position
                item.save(update_fields=("order",))
    return True


def move_module(module, direction):
    """Move a module within its draft course. Returns True when moved."""
    from learning.models import Module

    siblings = Module.objects.filter(programme_version=module.programme_version).order_by("order", "title")
    return _move(siblings, module, direction)


def move_lesson(lesson, direction):
    """Move a lesson within its own module. Returns True when moved."""
    siblings = Lesson.objects.filter(module=lesson.module).order_by("order", "title")
    return _move(siblings, lesson, direction)
