"""Compact Jalali month grid for /appointments/."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import jdatetime

from apps.staff.calendar_colors import MAX_MONTH_DAY_DOTS, resolve_staff_calendar_color
from apps.core.utils.dates import (
    JALALI_WEEKDAY_LABELS_FA,
    _jalali_days_in_month,
    jalali_weekday,
)


def staff_dots_by_day(
    appointments,
) -> dict[date, list[int]]:
    """Map Gregorian day -> sorted unique staff ids with appointments that day."""
    from django.utils import timezone

    by_day: dict[date, set[int]] = defaultdict(set)
    for appt in appointments:
        if not appt.staff_id:
            continue
        local_day = timezone.localtime(appt.start_at).date()
        by_day[local_day].add(appt.staff_id)
    return {d: sorted(ids) for d, ids in by_day.items()}


def build_jalali_month_grid(
    jy: int,
    jm: int,
    *,
    today: date,
    selected_day: date | None,
    dots_by_day: dict[date, list[int]],
    staff_colors: dict[int, str] | None = None,
    selected_staff_color: str | None = None,
) -> dict:
    staff_colors = staff_colors or {}
    days_in_month = _jalali_days_in_month(jy, jm)
    first_g = jdatetime.date(jy, jm, 1).togregorian()
    lead = jalali_weekday(first_g)

    cells: list[dict] = []
    for _ in range(lead):
        cells.append({"pad": True})

    for jd in range(1, days_in_month + 1):
        g = jdatetime.date(jy, jm, jd).togregorian()
        staff_ids = dots_by_day.get(g, [])
        visible_ids = staff_ids[:MAX_MONTH_DAY_DOTS]
        extra_dot_count = max(0, len(staff_ids) - len(visible_ids))
        is_selected = bool(selected_day and g == selected_day)
        cells.append(
            {
                "pad": False,
                "jd": jd,
                "gregorian": g,
                "iso": g.isoformat(),
                "is_today": g == today,
                "is_selected": is_selected,
                "selected_tint": selected_staff_color if is_selected and selected_staff_color else "",
                "dots": [
                    {
                        "staff_id": sid,
                        "color": staff_colors.get(sid) or resolve_staff_calendar_color(None, staff_id=sid),
                    }
                    for sid in visible_ids
                ],
                "dots_extra": extra_dot_count,
            }
        )

    while len(cells) % 7:
        cells.append({"pad": True})

    return {
        "cells": cells,
        "weekday_labels": list(JALALI_WEEKDAY_LABELS_FA),
    }