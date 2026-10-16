"""Presentation context shared by every rendered page."""


def guided_practical(request):
    """The guide panel for a guided-practice step, on the simulator page it points at.

    Read-only, and quiet unless the student is actually standing on a step: the
    resolver matches the page against the student's own in-progress attempt
    before it builds anything.
    """
    from .guides import guide_panel

    return guide_panel(request)
