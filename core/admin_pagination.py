"""Configurable page sizes for Unfold changelists.

Adds a shared `page_size` GET parameter (10/20/50/100/200) to every
ModelAdmin that mixes in PageSizesMixin. The value is applied to the
changelist's paginator before results are computed, so pagination stays
fully server-side. Page navigation keeps the chosen size automatically:
Django's ChangeList builds pagination links from every query parameter
except the page number itself.
"""

from django.contrib.admin.views.main import ChangeList

from unfold.admin import ModelAdmin as UnfoldModelAdmin

PAGE_SIZE_PARAM = "page_size"
PAGE_SIZE_OPTIONS = (10, 20, 50, 100, 200)
DEFAULT_PAGE_SIZE = 100


def requested_page_size(request):
    """The page size asked for in the query string, or None. Only the
    whitelisted options are honoured; anything else falls back to the
    ModelAdmin default."""
    raw = request.GET.get(PAGE_SIZE_PARAM, "")
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return None
    return size if size in PAGE_SIZE_OPTIONS else None


class PageSizeChangeList(ChangeList):
    def __init__(self, request, *args, **kwargs):
        # Django's changelist validates every query parameter against the
        # model's filters and bounces unknown ones to ?e=1, so the page
        # size is removed from the request before validation and restored
        # to the link-building params afterwards.
        self._page_size = requested_page_size(request)
        if PAGE_SIZE_PARAM in request.GET:
            # Removed even when invalid: an unrecognised value must fall
            # back to the default page size, not trip the changelist's
            # unknown-parameter error redirect.
            get = request.GET.copy()
            get.pop(PAGE_SIZE_PARAM, None)
            request.GET = get
        super().__init__(request, *args, **kwargs)
        if self._page_size is not None:
            value = str(self._page_size)
            self.params[PAGE_SIZE_PARAM] = value
            self.filter_params[PAGE_SIZE_PARAM] = value

    def get_results(self, request):
        # Applied here rather than in __init__ because the parent computes
        # the results (and builds the paginator) inside its own __init__.
        if self._page_size is not None:
            self.list_per_page = self._page_size
        super().get_results(request)


class PageSizesMixin:
    """Mixin for unfold ModelAdmins: enables the page-size selector on the
    changelist. list_per_page stays the ModelAdmin default (100) until the
    user picks a size."""

    page_size_options = PAGE_SIZE_OPTIONS

    def get_changelist(self, request, **kwargs):
        return PageSizeChangeList


class ModelAdmin(PageSizesMixin, UnfoldModelAdmin):
    """Project base for every unfold ModelAdmin: identical behaviour plus
    the configurable page-size selector on its changelist."""
