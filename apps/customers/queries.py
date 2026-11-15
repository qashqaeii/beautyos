from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer


def filter_customers(salon, *, q="", segment="", tag_id=None, ordering="-created_at"):
    qs = Customer.scoped(salon).filter(is_deleted=False).prefetch_related("tags")

    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))

    if tag_id:
        qs = qs.filter(tags__id=tag_id)

    now = timezone.now()
    if segment == "new":
        qs = qs.filter(total_visits=0)
    elif segment == "vip":
        qs = qs.filter(is_vip=True)
    elif segment == "active":
        qs = qs.filter(last_visit_at__gte=now - timedelta(days=30))
    elif segment == "inactive_30":
        qs = qs.filter(
            Q(last_visit_at__lt=now - timedelta(days=30)) | Q(last_visit_at__isnull=True),
            total_visits__gt=0,
        )
    elif segment == "inactive_60":
        qs = qs.filter(
            Q(last_visit_at__lt=now - timedelta(days=60)) | Q(last_visit_at__isnull=True)
        )
    elif segment == "upcoming":
        customer_ids = (
            Appointment.scoped(salon)
            .filter(
                start_at__gte=now,
                status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED],
            )
            .values_list("customer_id", flat=True)
        )
        qs = qs.filter(pk__in=customer_ids)

    allowed = {
        "name": "full_name",
        "-name": "-full_name",
        "last_visit": "last_visit_at",
        "-last_visit": "-last_visit_at",
        "visits": "total_visits",
        "-visits": "-total_visits",
        "created": "created_at",
        "-created": "-created_at",
    }
    qs = qs.order_by(allowed.get(ordering, "-created_at"))
    return qs.distinct()
