"""Toman amount parsing and display (matches ``fa_money`` / JS ``formatTomanFa``)."""

from __future__ import annotations

import re

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def parse_toman_input(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip().translate(_PERSIAN_DIGITS)
    s = re.sub(r"[.,،٬\s]", "", s)
    s = s.replace("تومان", "").replace("ریال", "")
    s = "".join(c for c in s if c.isdigit())
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def format_toman_fa(value) -> str:
    if value is None:
        return ""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ""
    s = f"{n:,}".replace(",", ".")
    return s.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
