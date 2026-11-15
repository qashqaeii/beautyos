from django import template

from apps.staff.display import staff_booking_label

register = template.Library()


@register.filter
def staff_booking_label_filter(staff):
    if staff is None:
        return ""
    return staff_booking_label(staff)
