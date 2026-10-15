from django import template
from django.utils.safestring import mark_safe

from learning.rich_text import to_safe_html

register = template.Library()


@register.filter(name="rich_content")
def rich_content(value):
    """Render a lesson content body as safe HTML, whatever form it is stored in."""
    return mark_safe(to_safe_html(value))
