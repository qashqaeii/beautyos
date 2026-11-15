"""Staff calendar accent colors (month view, filters, appointment list)."""

from __future__ import annotations

import re

from apps.staff.models import StaffProfile

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

STAFF_CALENDAR_PALETTE: tuple[str, ...] = (
    "#BBA5CB",
    "#A8BFA5",
    "#9CB6C5",
    "#B99183",
    "#D5BC83",
)

CALENDAR_COLOR_CHOICES: tuple[tuple[str, str], ...] = (
    ("", "پیش‌فرض (خودکار)"),
    ("#BBA5CB", "یاسی ملایم"),
    ("#A8BFA5", "سبز مریم‌گلی"),
    ("#9CB6C5", "آبی خاکستری"),
    ("#B99183", "موکا"),
    ("#D5BC83", "طلایی مات"),
)

MAX_MONTH_DAY_DOTS = 4


def normalize_calendar_color(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if HEX_RE.match(value):
        return value.upper()
    return None


def default_calendar_color_for_id(staff_id: int) -> str:
    return STAFF_CALENDAR_PALETTE[staff_id % len(STAFF_CALENDAR_PALETTE)]


def resolve_staff_calendar_color(staff: StaffProfile | None, *, staff_id: int | None = None) -> str:
    if staff is not None:
        custom = normalize_calendar_color(staff.calendar_color)
        if custom:
            return custom
        return default_calendar_color_for_id(staff.pk)
    return default_calendar_color_for_id(staff_id or 0)


def staff_color_map(staff_list: list[StaffProfile]) -> dict[int, str]:
    return {s.pk: resolve_staff_calendar_color(s) for s in staff_list}