from datetime import date, datetime
import re

import jdatetime
from django.utils import timezone


def to_jalali(d: date | datetime | None) -> str:
    if d is None:
        return ""
    if isinstance(d, datetime):
        if timezone.is_aware(d):
            d = timezone.localtime(d)
        d = d.date()
    jd = jdatetime.date.fromgregorian(date=d)
    return jd.strftime("%Y/%m/%d")


def to_jalali_datetime(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    jd = jdatetime.datetime.fromgregorian(datetime=dt)
    return jd.strftime("%Y/%m/%d %H:%M")


def today_jalali_label() -> str:
    return to_jalali(timezone.localdate())


def _normalize_digits(raw: str) -> str:
    return (
        str(raw)
        .strip()
        .translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
        .replace("ي", "ی")
        .replace("ك", "ک")
    )


def parse_jalali_date(raw: str) -> date:
    """Parse Jalali YYYY/MM/DD (Persian or Latin digits) to Gregorian date."""
    if not raw or not str(raw).strip():
        raise ValueError("تاریخ نامعتبر است.")
    text = _normalize_digits(raw)
    text = text.replace("-", "/").replace(".", "/")
    parts = [p for p in text.split("/") if p]
    if len(parts) != 3:
        raise ValueError("قالب تاریخ باید YYYY/MM/DD باشد.")
    try:
        jy, jm, jd = (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError as exc:
        raise ValueError("تاریخ نامعتبر است.") from exc
    try:
        return jdatetime.date(jy, jm, jd).togregorian()
    except ValueError as exc:
        raise ValueError("تاریخ نامعتبر است.") from exc


def parse_jalali_date_loose(raw: str) -> date | None:
    try:
        return parse_jalali_date(raw)
    except ValueError:
        return None


def _jalali_days_in_month(year: int, month: int) -> int:
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if jdatetime.date(year, 1, 1).isleap() else 29


def jalali_month_bounds(reference: date | None = None) -> tuple[date, date]:
    ref = reference or timezone.localdate()
    jd = jdatetime.date.fromgregorian(date=ref)
    start = jdatetime.date(jd.year, jd.month, 1).togregorian()
    end = jdatetime.date(jd.year, jd.month, _jalali_days_in_month(jd.year, jd.month)).togregorian()
    return start, end


def jalali_three_previous_months_bounds(reference: date | None = None) -> tuple[date, date]:
    ref = reference or timezone.localdate()
    jd = jdatetime.date.fromgregorian(date=ref)
    end_month = jd.month - 1
    end_year = jd.year
    if end_month < 1:
        end_month = 12
        end_year -= 1
    end = jdatetime.date(end_year, end_month, _jalali_days_in_month(end_year, end_month)).togregorian()

    start_month = jd.month - 3
    start_year = jd.year
    while start_month < 1:
        start_month += 12
        start_year -= 1
    start = jdatetime.date(start_year, start_month, 1).togregorian()
    return start, end


def jalali_range_label(start: date, end: date) -> str:
    if start == end:
        return to_jalali(start)
    return f"{to_jalali(start)} – {to_jalali(end)}"


def week_start_saturday(d: date) -> date:
    """Saturday-based week start (matches StaffWorkHours.Weekday)."""
    from datetime import timedelta

    return d - timedelta(days=(d.weekday() + 2) % 7)


def staff_weekday_for_date(d: date) -> int:
    """Map Gregorian date to StaffWorkHours weekday (0=Saturday … 6=Friday)."""
    return (d.weekday() + 2) % 7


JALALI_MONTH_NAMES_FA = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

JALALI_WEEKDAY_LABELS_FA = ("ش", "ی", "د", "س", "چ", "پ", "ج")


def jalali_weekday(d: date) -> int:
    """Saturday=0 … Friday=6."""
    return (d.weekday() + 2) % 7


def jalali_ym_for_date(d: date) -> tuple[int, int]:
    jd = jdatetime.date.fromgregorian(date=d)
    return jd.year, jd.month


def add_jalali_months(jy: int, jm: int, delta: int) -> tuple[int, int]:
    idx = jy * 12 + (jm - 1) + delta
    new_jy = idx // 12
    new_jm = idx % 12 + 1
    return new_jy, new_jm


def parse_jalali_month_param(raw: str | None, fallback: date | None = None) -> tuple[int, int]:
    ref = fallback or timezone.localdate()
    default_jd = jdatetime.date.fromgregorian(date=ref)
    if not raw or not str(raw).strip():
        return default_jd.year, default_jd.month
    text = _normalize_digits(str(raw)).replace("/", "-")
    parts = [p for p in text.split("-") if p]
    if len(parts) < 2:
        return default_jd.year, default_jd.month
    try:
        jy, jm = int(parts[0]), int(parts[1])
    except ValueError:
        return default_jd.year, default_jd.month
    if not (1200 <= jy <= 1600 and 1 <= jm <= 12):
        return default_jd.year, default_jd.month
    return jy, jm


def jalali_month_query_value(jy: int, jm: int) -> str:
    return f"{jy}-{jm:02d}"


def gregorian_bounds_for_jalali_month(jy: int, jm: int) -> tuple[date, date]:
    start = jdatetime.date(jy, jm, 1).togregorian()
    end = jdatetime.date(jy, jm, _jalali_days_in_month(jy, jm)).togregorian()
    return start, end


def date_in_jalali_month(d: date, jy: int, jm: int) -> bool:
    jd = jdatetime.date.fromgregorian(date=d)
    return jd.year == jy and jd.month == jm
