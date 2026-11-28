"""Cross-salon product adoption metrics for the central reports page.

Counts are aggregated by salon and time window; no personal data is returned.
"""
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.salons.models import Salon
from apps.platform_admin.models import PlatformActivityEvent


def product_performance(days=30, now=None):
    if days not in (7, 30, 90):
        raise ValueError("Unsupported reporting period")
    now = now or timezone.now()
    start = now - timedelta(days=days)
    previous = start - timedelta(days=days)
    current = _window(start, now)
    prior = _window(previous, start)
    rows = [
        ("customers", "مشتریان جدید"),
        ("appointments", "نوبت‌های جدید"),
        ("online", "رزروهای اینترنتی"),
    ]
    comparison = [
        {
            "key": key, "label": label,
            "current": current[key], "previous": prior[key],
            "difference": current[key] - prior[key],
        }
        for key, label in rows
    ]
    return {
        "comparison": comparison,
        "online_share": round(100 * current["online"] / current["appointments"], 1)
        if current["appointments"] else None,
        "active_booking_salons": current["booking_salons"],
        "active_customer_salons": current["customer_salons"],
        "salons_total": Salon.objects.count(),
        "coverage_note": "این آمار براساس رکوردهای موجود محاسبه می‌شود؛ حذف‌های دائمی و واردسازی‌های تاریخی ممکن است بر مقایسه اثر بگذارند.",
    }


def _window(start, end):
    bookings = Appointment.objects.filter(created_at__gte=start, created_at__lt=end)
    customers = Customer.objects.filter(created_at__gte=start, created_at__lt=end)
    booking_stats = bookings.aggregate(
        appointments=Count("pk"),
        online=Count("pk", filter=Q(source=Appointment.Source.PUBLIC)),
        booking_salons=Count("salon_id", distinct=True),
    )
    return {
        **booking_stats,
        "customers": customers.count(),
        "customer_salons": customers.values("salon_id").distinct().count(),
    }


def salon_product_performance(*, salon, days=30, now=None):
    """Same-window comparisons scoped to a single salon; no personal records."""
    if days not in (7, 30, 90):
        raise ValueError("Unsupported reporting period")
    now = now or timezone.now()
    start = now - timedelta(days=days)
    previous = start - timedelta(days=days)

    def snapshot(begin, end):
        bookings = Appointment.objects.filter(
            salon=salon, created_at__gte=begin, created_at__lt=end,
        )
        stats = bookings.aggregate(
            appointments=Count("pk"),
            online=Count("pk", filter=Q(source=Appointment.Source.PUBLIC)),
        )
        return {
            **stats,
            "customers": Customer.objects.filter(
                salon=salon, created_at__gte=begin, created_at__lt=end,
            ).count(),
        }

    current = snapshot(start, now)
    prior = snapshot(previous, start)
    return {
        "days": days,
        "comparison": [
            {
                "label": label, "current": current[key],
                "previous": prior[key], "difference": current[key] - prior[key],
            }
            for key, label in (
                ("appointments", "نوبت‌های ثبت‌شده"),
                ("online", "رزروهای اینترنتی"),
                ("customers", "مشتریان جدید"),
            )
        ],
        "online_share": (
            round(100 * current["online"] / current["appointments"], 1)
            if current["appointments"] else None
        ),
        "coverage_note": "شاخص‌ها براساس تاریخ ایجاد رکورد محاسبه شده‌اند؛ تاریخ انجام نوبت معیار این گزارش نیست.",
    }


def salon_feature_adoption(*, salon, days=30, now=None):
    """Feature adoption by event kind; zero counts are meaningful only for tracked kinds."""
    if days not in (7, 30, 90):
        raise ValueError("Unsupported reporting period")
    now = now or timezone.now()
    start = now - timedelta(days=days)
    previous = start - timedelta(days=days)
    events = PlatformActivityEvent.objects.filter(salon=salon)
    current = dict(events.filter(
        occurred_at__gte=start, occurred_at__lt=now,
    ).values("kind").annotate(total=Sum("count")).values_list("kind", "total"))
    prior = dict(events.filter(
        occurred_at__gte=previous, occurred_at__lt=start,
    ).values("kind").annotate(total=Sum("count")).values_list("kind", "total"))
    supported = (
        PlatformActivityEvent.Kind.APPOINTMENT_CREATED,
        PlatformActivityEvent.Kind.APPOINTMENT_COMPLETED,
        PlatformActivityEvent.Kind.CUSTOMER_CREATED,
        PlatformActivityEvent.Kind.STAFF_CREATED,
        PlatformActivityEvent.Kind.INVOICE_CREATED,
    )
    labels = dict(PlatformActivityEvent.Kind.choices)
    return [
        {
            "label": labels[kind], "current": current.get(kind, 0),
            "previous": prior.get(kind, 0),
            "difference": current.get(kind, 0) - prior.get(kind, 0),
        }
        for kind in supported
    ]
