"""Rich-text storage and rendering rules for lesson content bodies.

A ``ContentBlock.body`` is either legacy plain text or the HTML produced by the
instructor section editor. Both branches converge on the same sanitised HTML, so
every renderer can insert the stored value directly and word counts read the same
text a learner sees.
"""

from __future__ import annotations

import html as html_lib
import re

import nh3
from django.utils.html import linebreaks as _linebreaks

ALLOWED_TAGS = frozenset(
    {
        "p", "br", "hr", "h3", "h4", "ul", "ol", "li", "blockquote",
        "strong", "em", "a", "table", "thead", "tbody", "tr", "th", "td",
        "caption", "figure", "figcaption", "img",
    }
)
ALLOWED_ATTRIBUTES = {
    "a": frozenset({"href", "title"}),
    "img": frozenset({"src", "alt", "width", "height"}),
    "th": frozenset({"scope", "colspan", "rowspan"}),
    "td": frozenset({"colspan", "rowspan"}),
    "ol": frozenset({"start"}),
}
ALLOWED_URL_SCHEMES = frozenset({"https", "http", "mailto"})
# Stripped together with their contents; ``tags`` alone would keep the inner text.
CONTENT_FREE_TAGS = frozenset({"script", "style", "iframe", "object", "embed", "svg", "noscript", "template"})

_TAG_MARKUP = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^>]*)?/?>|<!--")
_TAG_STRIP = re.compile(r"<[^>]*>")


def is_html(value: str) -> bool:
    """True when the body carries tag markup and should be treated as rich text."""
    return bool(_TAG_MARKUP.search(value or ""))


def to_safe_html(value: str) -> str:
    """Return HTML that is safe to insert into a lesson page.

    Plain-text bodies keep Django's ``linebreaks`` behaviour, so existing lessons
    render exactly as they did before. Bodies that carry markup are sanitised down
    to the allowlist above; the result contains no remaining tags, so re-sanitising
    it is a no-op.
    """
    text = value or ""
    if not is_html(text):
        # autoescape=True is what the template filter passes, so stored text and
        # the old ``{{ block.body|linebreaks }}`` output match exactly.
        return str(_linebreaks(text, autoescape=True))
    return nh3.clean(
        text,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        clean_content_tags=CONTENT_FREE_TAGS,
        strip_comments=True,
        link_rel="noopener noreferrer",
    )


def plain_text(value: str) -> str:
    """Return the readable text of a body with all markup and entities resolved."""
    text = value or ""
    if is_html(text):
        text = _TAG_STRIP.sub(" ", text)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def count_words(value: str) -> int:
    """Count the words a learner actually reads, ignoring markup."""
    return len(plain_text(value).split())
