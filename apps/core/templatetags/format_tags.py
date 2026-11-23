from datetime import date, datetime
import json

from django.utils.safestring import mark_safe

import jdatetime
from django import template
from django.utils import timezone

register = template.Library()

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_WEEKDAYS_FA = (
    "شنبه",
    "یکشنبه",
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنجشنبه",
    "جمعه",
)


@register.filter
def persian_digits(value) -> str:
    if value is None:
        return ""
    return str(value).translate(_PERSIAN_DIGITS)


@register.filter
def jalali_date(value) -> str:
    from apps.core.utils.dates import to_jalali

    return to_jalali(value)


@register.filter
def jalali_datetime(value) -> str:
    from apps.core.utils.dates import to_jalali_datetime

    return to_jalali_datetime(value)


@register.filter
def fa_jalali(value) -> str:
    return persian_digits(jalali_date(value))


@register.filter
def fa_jalali_datetime(value) -> str:
    return persian_digits(jalali_datetime(value))


@register.filter
def fa_money(value) -> str:
    if value is None:
        return ""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return persian_digits(str(value))
    s = f"{n:,}".replace(",", ".")
    return persian_digits(s)


@register.filter
def fa_num(value) -> str:
    return persian_digits(value)


@register.filter
def fa_time(value) -> str:
    if not value:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return persian_digits(value.strftime("%H:%M"))


@register.filter
def fa_weekday(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        value = value.date()
    if not isinstance(value, date):
        return ""
    jd = jdatetime.date.fromgregorian(date=value)
    return _WEEKDAYS_FA[jd.weekday()]

@register.filter
def jsonld(value):
    """Protect JSON-LD text from script-termination or HTML injection."""
    if not value:
        return ""
    return mark_safe(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", r"\u003C").replace(">", r"\u003E").replace("&", r"\u0026")
    )
