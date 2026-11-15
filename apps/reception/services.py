from datetime import datetime, timedelta

from django.utils import timezone

from apps.appointments.models import Appointment
from apps.retention.models import FollowUp


def get_reception_desk_context(salon, *, appointment_qs):
    today = timezone.localdate()
    start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    end = start + timedelta(days=1)
    today_qs = appointment_qs.filter(start_at__gte=start, start_at__lt=end).order_by("start_at")

    summary = {
        "today_total": today_qs.count(),
        "checked_in": today_qs.filter(status=Appointment.Status.CHECKED_IN).count(),
        "pending": today_qs.filter(status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED]).count(),
        "cancelled": today_qs.filter(status=Appointment.Status.CANCELLED).count(),
        "no_show": today_qs.filter(status=Appointment.Status.NO_SHOW).count(),
    }
    follow_ups = FollowUp.scoped(salon).filter(status=FollowUp.Status.OPEN).select_related("customer")[:10]
    queue = today_qs.select_related("customer", "staff", "service")
    return {"summary": summary, "queue": queue, "follow_ups": follow_ups, "today": today}
