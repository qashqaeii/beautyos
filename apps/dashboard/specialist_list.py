"""Context builders for the reception specialists directory."""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone

from apps.appointments.services.calendar_day_grid import staff_color_class
from apps.staff.models import StaffProfile, StaffTimeOff, StaffWorkHours


def _local_weekday(d: date) -> int:
    return (d.weekday() + 2) % 7


def _on_leave(staff: StaffProfile, day: date) -> bool:
    return StaffTimeOff.objects.filter(
        staff=staff,
        start_date__lte=day,
        end_date__gte=day,
    ).exists()


def _hours_for_day(staff: StaffProfile, day: date) -> StaffWorkHours | None:
    weekday = _local_weekday(day)
    return staff.work_hours.filter(weekday=weekday).first()


def today_hours_label(staff: StaffProfile, today: date) -> tuple[str, str]:
    """Return (kind, label) where kind is status|leave|closed|none."""
    if _on_leave(staff, today):
        return "leave", "مرخصی"
    hours = _hours_for_day(staff, today)
    if hours is None:
        return "none", "ساعت کاری ثبت نشده"
    if hours.is_closed:
        return "closed", "تعطیل"
    return (
        "open",
        f"{hours.start_time.strftime('%H:%M')}–{hours.end_time.strftime('%H:%M')}",
    )


def build_specialist_rows(
    profiles: list[StaffProfile],
    *,
    week_start: date,
    today: date | None = None,
) -> list[dict]:
    today = today or timezone.localdate()
    rows = []
    for profile in profiles:
        services = list(
            profile.services.filter(is_active=True, is_deleted=False).order_by("name")
        )
        kind, today_label = today_hours_label(profile, today)
        week_lines = []
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            if _on_leave(profile, day):
                hours_text = "مرخصی"
            else:
                wh = _hours_for_day(profile, day)
                if wh is None:
                    hours_text = "ثبت نشده"
                elif wh.is_closed:
                    hours_text = "تعطیل"
                else:
                    hours_text = (
                        f"{wh.start_time.strftime('%H:%M')}–{wh.end_time.strftime('%H:%M')}"
                    )
            day_name = StaffWorkHours.Weekday(offset).label
            from apps.core.utils.dates import to_jalali

            week_lines.append(
                {
                    "day_name": day_name,
                    "jalali": to_jalali(day),
                    "hours_text": hours_text,
                    "is_today": day == today,
                }
            )
        rows.append(
            {
                "profile": profile,
                "services": services,
                "service_count": len(services),
                "service_extra": max(0, len(services) - 3),
                "color_class": staff_color_class(profile.pk),
                "today_kind": kind,
                "today_label": today_label,
                "week_lines": week_lines,
                "can_reserve": profile.is_bookable and len(services) > 0,
            }
        )
    return rows