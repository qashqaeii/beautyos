"""Prioritised, explainable follow-up queue for central operators.

Signals are operational hints, not churn predictions. Queries aggregate across
salons; never expose tenant customer details or invoice values.
"""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.platform_admin.models import PlatformActivityEvent, SalonSubscription, SupportTicket
from apps.salons.models import Salon


def followup_queue(*, now=None, limit=12):
    now = now or timezone.now()
    current_start = now - timedelta(days=30)
    previous_start = current_start - timedelta(days=30)
    recent = set(PlatformActivityEvent.objects.filter(
        occurred_at__gte=current_start, occurred_at__lt=now,
    ).values_list("salon_id", flat=True).distinct())
    previous = set(PlatformActivityEvent.objects.filter(
        occurred_at__gte=previous_start, occurred_at__lt=current_start,
    ).values_list("salon_id", flat=True).distinct())
    subscriptions = {
        item.salon_id: item for item in
        SalonSubscription.objects.select_related("plan").all()
    }
    open_counts = dict(
        SupportTicket.objects.filter(
            status__in=[SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS],
        ).values("salon_id").annotate(total=Count("pk")).values_list("salon_id", "total")
    )
    queue = []
    for salon in Salon.objects.select_related("settings").all().iterator():
        reasons = []
        if open_counts.get(salon.pk, 0):
            reasons.append("پشتیبانی باز")
        if not salon.settings.onboarding_completed_at:
            reasons.append("راه‌اندازی ناقص")
        if salon.pk in previous and salon.pk not in recent:
            reasons.append("افت فعالیت ثبت‌شده")
        subscription = subscriptions.get(salon.pk)
        if subscription and subscription.ends_at <= now:
            reasons.append("پایان تاریخ اشتراک")
        if not reasons:
            continue
        # Deterministic operational ordering, not a statistical health score.
        priority = (
            (4 if open_counts.get(salon.pk, 0) else 0)
            + (3 if subscription and subscription.ends_at <= now else 0)
            + (2 if salon.pk in previous and salon.pk not in recent else 0)
            + (1 if not salon.settings.onboarding_completed_at else 0)
        )
        queue.append({
            "salon": salon, "reasons": reasons, "priority": priority,
            "open_tickets": open_counts.get(salon.pk, 0),
        })
    queue.sort(key=lambda item: (-item["priority"], str(item["salon"].pk)))
    return {"total": len(queue), "items": queue[:limit]}
