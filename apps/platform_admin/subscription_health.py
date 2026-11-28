"""Subscription lifecycle intelligence without treating subscription state as payment.

This module never charges, renews, or changes entitlements.
"""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.platform_admin.models import SalonSubscription


def subscription_health(*, now=None, horizon_days=7):
    if horizon_days < 1 or horizon_days > 90:
        raise ValueError("Invalid expiry horizon")
    now = now or timezone.now()
    horizon = now + timedelta(days=horizon_days)
    qs = SalonSubscription.objects.all()
    # Status and validity are deliberately separate: stale ACTIVE records
    # must not be counted as currently valid subscriptions.
    valid = qs.filter(
        status=SalonSubscription.Status.ACTIVE,
        starts_at__lte=now, ends_at__gt=now,
    )
    expiring = valid.filter(ends_at__lte=horizon)
    stale = qs.filter(
        status__in=[SalonSubscription.Status.ACTIVE, SalonSubscription.Status.TRIAL],
        ends_at__lte=now,
    )
    return {
        "valid_active": valid.count(),
        "expiring_soon": expiring.count(),
        "expired_dates_unreconciled": stale.count(),
        "past_due": qs.filter(status=SalonSubscription.Status.PAST_DUE).count(),
        "trial_valid": qs.filter(
            status=SalonSubscription.Status.TRIAL,
            starts_at__lte=now, ends_at__gt=now,
            trial_ends_at__gt=now,
        ).count(),
        "expiring_salons": list(
            expiring.select_related("salon", "plan").order_by("ends_at", "pk")[:12]
        ),
        "stale_salons": list(
            stale.select_related("salon", "plan").order_by("ends_at", "pk")[:12]
        ),
        "horizon_days": horizon_days,
    }
