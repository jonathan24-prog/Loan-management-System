from django import template
from django.contrib.humanize.templatetags.humanize import intcomma

register = template.Library()

@register.filter
def peso(value):
    try:
        value = float(value)
        return f"₱{intcomma(f'{value:,.2f}')}"
    except (ValueError, TypeError):
        return "₱0.00"