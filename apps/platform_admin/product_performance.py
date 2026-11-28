"""Cross-salon product adoption metrics for the central reports page.

Counts are aggregated by salon and time window; no personal data is returned.
"""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.salons.models import Salon


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
