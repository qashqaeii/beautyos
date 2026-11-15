from datetime import timedelta

from django.db.models import Max
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.retention.models import FollowUp
from apps.salons.models import SalonSettings


def sync_follow_up_queue(salon):
    settings = salon.settings
    thresholds = [
        (settings.retention_days_30, "۳۰ روز بدون مراجعه"),
        (settings.retention_days_60, "۶۰ روز بدون مراجعه"),
        (settings.retention_days_90, "۹۰ روز بدون مراجعه"),
    ]
    today = timezone.localdate()
    customers = Customer.scoped(salon).filter(is_deleted=False)
    for customer in customers:
        last = customer.last_visit_at
        if last is None:
            days = (timezone.now() - customer.created_at).days
        else:
            days = (timezone.now() - last).days
        matched = None
        for days_limit, reason in thresholds:
            if days >= days_limit:
                matched = reason
        if not matched:
            continue
        FollowUp.objects.get_or_create(
            salon=salon,
            customer=customer,
            status=FollowUp.Status.OPEN,
            defaults={
                "reason": matched,
                "days_since_visit": days,
                "priority": FollowUp.Priority.HIGH if days >= settings.retention_days_90 else FollowUp.Priority.MEDIUM,
            },
        )
