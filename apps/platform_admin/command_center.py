"""Command center metrics: explicitly scoped, never confuse usage with billing."""
from datetime import timedelta

from django.utils import timezone
from django.db.models import Sum
from django.db.models.functions import TruncDate

from apps.platform_admin.activity_metrics import activity_retention, usage_summary
from apps.platform_admin.models import PlatformActivityEvent, SalonSubscription


def command_center_snapshot(days=30, now=None):
    if days not in (7, 30, 90):
        raise ValueError("Unsupported period")
    now = now or timezone.now()
    start = now - timedelta(days=days)
    previous = start - timedelta(days=days)
    current = usage_summary(since=start, until=now)
    earlier = usage_summary(since=previous, until=start)
    retention = activity_retention(
        cohort_start=previous, cohort_end=start, return_start=start, return_end=now,
    )
    active_ids = PlatformActivityEvent.objects.filter(
        occurred_at__gte=start, occurred_at__lt=now,
    ).values("salon_id").distinct()
    # At-risk means a previously observed salon has no event in the current
    # period. This is NOT a prediction of churn or a subscription cancellation.
    inactive_prior = PlatformActivityEvent.objects.filter(
        occurred_at__gte=previous, occurred_at__lt=start,
    ).exclude(salon_id__in=active_ids).values("salon_id").distinct().count()
    by_kind = {item["kind"]: item for item in current["by_kind"]}
    features = [
        {"label": label, "count": by_kind.get(kind, {}).get("total", 0),
         "salons": by_kind.get(kind, {}).get("salons", 0)}
        for kind, label in PlatformActivityEvent.Kind.choices
    ]
    subscribed = SalonSubscription.objects.filter(
        status=SalonSubscription.Status.ACTIVE, starts_at__lte=now, ends_at__gt=now,
    ).count()
    # Calendar-day buckets in the configured local timezone. The reporting\n    # window itself remains a rolling interval, so it may touch days+1 dates.
    series = list(PlatformActivityEvent.objects.filter(
        occurred_at__gte=start, occurred_at__lt=now,
    ).annotate(day=TruncDate("occurred_at")).values("day").annotate(
        total=Sum("count"),
    ).order_by("day"))
    counts = {item["day"]: item["total"] for item in series}
    trend = []
    first_day = timezone.localtime(start).date()
    last_day = timezone.localtime(now).date()
    for index in range((last_day - first_day).days + 1):
        day = first_day + timedelta(days=index)
        trend.append({"date": day, "count": counts.get(day, 0)})
    maximum = max((item["count"] for item in trend), default=0)
    for item in trend:
        item["height"] = max(3, round(100 * item["count"] / maximum)) if item["count"] and maximum else 0
    return {
        "trend": trend,
        "usage_active": current["active_salons"],
        "usage_previous": earlier["active_salons"],
        "usage_events": current["events"],
        "retention": retention["retention_percent"],
        "cohort_size": retention["cohort_salons"],
        "retained": retention["retained_salons"],
        "prior_inactive": inactive_prior,
        "subscription_active": subscribed,
        "features": features,
        "coverage_note": "ثبت نوبت، مشتری، متخصص و فاکتور جدید ردیابی می‌شوند؛ سایر تعاملات و رویدادهای قدیمی پوشش کامل ندارند.",
        "revenue_note": "درآمد اشتراک BeautyOS هنوز قابل محاسبه نیست؛ پرداخت‌های سالن درآمد پلتفرم محسوب نمی‌شوند.",
    }
