from django import template

from apps.appointments.services.calendar_day_grid import staff_color_class as _staff_color_class
from apps.staff.calendar_colors import resolve_staff_calendar_color

register = template.Library()

STATUS_BADGE = {
    "pending": "badge-pending",
    "confirmed": "badge-confirmed",
    "checked_in": "badge-confirmed",
    "completed": "badge-completed",
    "cancelled": "badge-cancelled",
    "no_show": "badge-cancelled",
}


@register.filter
def status_badge(status):
    return STATUS_BADGE.get(status, "badge-pending")


@register.filter
def staff_color_class(staff_id) -> str:
    try:
        pk = staff_id.pk if hasattr(staff_id, "pk") else staff_id
        return _staff_color_class(int(pk))
    except (TypeError, ValueError, AttributeError):
        return _staff_color_class(0)


@register.filter
def staff_calendar_color(staff) -> str:
    if staff is None:
        return resolve_staff_calendar_color(None, staff_id=0)
    return resolve_staff_calendar_color(staff)


@register.filter
def dict_item(mapping, key):
    if mapping is None:
        return []
    return mapping.get(key, [])
