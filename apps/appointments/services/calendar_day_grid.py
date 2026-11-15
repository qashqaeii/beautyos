"""Day-view calendar grid for /appointments/."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.dashboard.role_services import OCCUPYING_STATUSES
from apps.staff.models import StaffProfile, StaffTimeOff, StaffWorkHours

SLOT_MINUTES = 15
DEFAULT_GRID_START = time(8, 0)
DEFAULT_GRID_END = time(22, 0)

STAFF_COLOR_CLASSES = (
    "appt-cal-staff--lavender",
    "appt-cal-staff--peach",
    "appt-cal-staff--sage",
    "appt-cal-staff--mist",
    "appt-cal-staff--cream",
)


def _local_weekday(d: date) -> int:
    return (d.weekday() + 2) % 7


def _minutes_since_midnight(t: time) -> int:
    return t.hour * 60 + t.minute


def staff_color_class(staff_id: int) -> str:
    return STAFF_COLOR_CLASSES[staff_id % len(STAFF_COLOR_CLASSES)]


def _work_hours(staff: StaffProfile, day: date) -> StaffWorkHours | None:
    weekday = _local_weekday(day)
    hours = StaffWorkHours.objects.filter(staff=staff, weekday=weekday).first()
    if not hours or hours.is_closed:
        return None
    return hours


def _on_leave(staff: StaffProfile, day: date) -> bool:
    return StaffTimeOff.objects.filter(
        staff=staff,
        start_date__lte=day,
        end_date__gte=day,
    ).exists()


def _appt_status_label(appt: Appointment) -> str:
    return appt.get_status_display()


def _format_hm(dt: datetime) -> str:
    local = timezone.localtime(dt)
    return local.strftime("%H:%M")


def _row_for_local_minutes(minutes: int, grid_start_min: int) -> int:
    return (minutes - grid_start_min) // SLOT_MINUTES + 1


def _row_span(start_min: int, end_min: int) -> int:
    return max(1, (end_min - start_min + SLOT_MINUTES - 1) // SLOT_MINUTES)


def _book_query(
    *,
    day: date,
    staff_id: int,
    start: datetime,
    service_id: int | None,
) -> str:
    params = {
        "book": "1",
        "day": day.isoformat(),
        "staff": staff_id,
        "start": timezone.localtime(start).replace(microsecond=0).isoformat(),
    }
    if service_id:
        params["service"] = service_id
    return f"?{urlencode(params)}"


@dataclass
class GridSegment:
    type: str
    row_start: int
    row_span: int
    label: str = ""
    status_label: str = ""
    customer_name: str = ""
    service_name: str = ""
    time_range: str = ""
    detail_url: str = ""
    book_url: str = ""
    is_service_match: bool = False
    appt_id: int | None = None


def _column_segments(
    staff: StaffProfile,
    day: date,
    grid_start_min: int,
    grid_end_min: int,
    appts: list[Appointment],
    *,
    selected_service_id: int | None,
    can_book: bool,
) -> list[GridSegment]:
    segments: list[GridSegment] = []
    total_span = _row_span(grid_start_min, grid_end_min)

    if _on_leave(staff, day):
        return [
            GridSegment(
                type="leave",
                row_start=1,
                row_span=total_span,
                label="مرخصی",
            )
        ]

    hours = _work_hours(staff, day)
    if not hours:
        return [
            GridSegment(
                type="closed",
                row_start=1,
                row_span=total_span,
                label="خارج از ساعت کاری",
            )
        ]

    work_start = _minutes_since_midnight(hours.start_time)
    work_end = _minutes_since_midnight(hours.end_time)

    if work_start > grid_start_min:
        segments.append(
            GridSegment(
                type="closed",
                row_start=1,
                row_span=_row_span(grid_start_min, work_start),
                label="خارج از ساعت کاری",
            )
        )

    staff_appts = [
        a
        for a in appts
        if a.staff_id == staff.pk and a.status in OCCUPYING_STATUSES
    ]
    staff_appts.sort(key=lambda a: a.start_at)

    tz = timezone.get_current_timezone()
    cursor_min = work_start

    def add_free(free_start_min: int, free_end_min: int) -> None:
        if free_end_min <= free_start_min:
            return
        row_start = _row_for_local_minutes(free_start_min, grid_start_min)
        row_span = _row_span(free_start_min, free_end_min)
        book_url = ""
        if can_book:
            start_dt = timezone.make_aware(
                datetime.combine(day, time(free_start_min // 60, free_start_min % 60)),
                tz,
            )
            book_url = _book_query(
                day=day,
                staff_id=staff.pk,
                start=start_dt,
                service_id=selected_service_id,
            )
        segments.append(
            GridSegment(
                type="free",
                row_start=row_start,
                row_span=row_span,
                label="وقت آزاد",
                book_url=book_url,
            )
        )

    for appt in staff_appts:
        local_start = timezone.localtime(appt.start_at)
        local_end = timezone.localtime(appt.end_at)
        appt_start = local_start.hour * 60 + local_start.minute
        appt_end = local_end.hour * 60 + local_end.minute
        appt_start = max(appt_start, work_start)
        appt_end = min(appt_end, work_end)
        if appt_end <= appt_start:
            continue

        if appt_start > cursor_min:
            add_free(cursor_min, appt_start)

        row_start = _row_for_local_minutes(appt_start, grid_start_min)
        row_span = _row_span(appt_start, appt_end)
        is_match = selected_service_id is None or appt.service_id == selected_service_id

        if selected_service_id and not is_match:
            segments.append(
                GridSegment(
                    type="busy",
                    row_start=row_start,
                    row_span=row_span,
                    label="رزرو شده",
                    time_range=f"{_format_hm(appt.start_at)} – {_format_hm(appt.end_at)}",
                )
            )
        else:
            segments.append(
                GridSegment(
                    type="appointment",
                    row_start=row_start,
                    row_span=row_span,
                    customer_name=appt.customer.full_name,
                    service_name=appt.service.name,
                    status_label=_appt_status_label(appt),
                    time_range=f"{_format_hm(appt.start_at)} – {_format_hm(appt.end_at)}",
                    detail_url=reverse("appointments:detail", kwargs={"pk": appt.pk}),
                    is_service_match=bool(selected_service_id and is_match),
                    appt_id=appt.pk,
                )
            )
        cursor_min = max(cursor_min, appt_end)

    if cursor_min < work_end:
        add_free(cursor_min, work_end)

    if work_end < grid_end_min:
        segments.append(
            GridSegment(
                type="closed",
                row_start=_row_for_local_minutes(work_end, grid_start_min),
                row_span=_row_span(work_end, grid_end_min),
                label="خارج از ساعت کاری",
            )
        )

    return segments


def build_day_calendar_grid(
    day: date,
    staff_list: list[StaffProfile],
    appointments,
    *,
    selected_service_id: int | None = None,
    can_book: bool = False,
) -> dict:
    staff_list = list(staff_list)
    grid_start_min = _minutes_since_midnight(DEFAULT_GRID_START)
    grid_end_min = _minutes_since_midnight(DEFAULT_GRID_END)

    for staff in staff_list:
        hours = _work_hours(staff, day)
        if not hours:
            continue
        ws = _minutes_since_midnight(hours.start_time)
        we = _minutes_since_midnight(hours.end_time)
        grid_start_min = min(grid_start_min, ws)
        grid_end_min = max(grid_end_min, we)

    grid_start_min = (grid_start_min // SLOT_MINUTES) * SLOT_MINUTES
    grid_end_min = ((grid_end_min + SLOT_MINUTES - 1) // SLOT_MINUTES) * SLOT_MINUTES
    total_rows = _row_span(grid_start_min, grid_end_min)

    time_labels = []
    for m in range(grid_start_min, grid_end_min, 60):
        row = _row_for_local_minutes(m, grid_start_min)
        h, mn = divmod(m, 60)
        time_labels.append({"row": row, "label": f"{h:02d}:{mn:02d}"})

    appt_list = list(appointments)
    columns = []
    for staff in staff_list:
        segments = _column_segments(
            staff,
            day,
            grid_start_min,
            grid_end_min,
            appt_list,
            selected_service_id=selected_service_id,
            can_book=can_book,
        )
        columns.append(
            {
                "staff": staff,
                "color_class": staff_color_class(staff.pk),
                "segments": [seg.__dict__ for seg in segments],
            }
        )

    return {
        "grid_start_min": grid_start_min,
        "grid_end_min": grid_end_min,
        "slot_minutes": SLOT_MINUTES,
        "total_rows": total_rows,
        "time_labels": time_labels,
        "columns": columns,
    }