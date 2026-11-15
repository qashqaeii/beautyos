from decimal import Decimal

from django import template

from apps.core.templatetags.format_tags import persian_digits

register = template.Library()


@register.filter
def fa_qty(value) -> str:
    if value is None or value == "":
        return ""
    try:
        d = Decimal(value)
    except Exception:
        return persian_digits(str(value))
    if d == d.to_integral_value():
        return persian_digits(int(d))
    normalized = d.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return persian_digits(text)
