import re
from datetime import time

from django.core.exceptions import ValidationError

_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def to_ascii_digits(value: str) -> str:
    return (value or "").translate(_DIGIT_TRANSLATION)


def parse_hhmm(value: str) -> time:
    """Parse user time as 24h HH:mm; accepts Persian digits and compact 0900."""
    if value is None:
        raise ValidationError("فرمت ساعت نامعتبر است.")
    raw = to_ascii_digits(str(value).strip())
    if not raw:
        raise ValidationError("فرمت ساعت نامعتبر است.")

    compact = re.sub(r"\D", "", raw)
    if ":" in raw:
        parts = raw.split(":", 1)
        if len(parts) != 2:
            raise ValidationError("فرمت ساعت باید به شکل HH:mm باشد.")
        hour_part, minute_part = parts[0], parts[1]
        if not hour_part.isdigit() or not minute_part.isdigit():
            raise ValidationError("فرمت ساعت باید به شکل HH:mm باشد.")
        hour, minute = int(hour_part), int(minute_part)
    elif len(compact) == 4:
        hour, minute = int(compact[:2]), int(compact[2:])
    elif len(compact) == 3:
        hour, minute = int(compact[0]), int(compact[1:])
    else:
        raise ValidationError("فرمت ساعت باید به شکل HH:mm باشد.")

    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValidationError("فرمت ساعت باید به شکل HH:mm باشد.")
    return time(hour, minute)
