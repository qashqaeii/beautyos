"""Privacy-safe platform product analytics.

Usage events are not audit records, financial transactions, or subscription renewals.
Only allowlisted event kinds and aggregate counts are accepted.
"""
from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from apps.platform_admin.models import PlatformActivityEvent


def record_activity(*, salon, kind, dedupe_key=None, occurred_at=None):
    """Record a single business event; retry-safe when dedupe_key is provided.

    Call from an already-successful business operation (or via transaction.on_commit).
    Never pass personal information as a dedupe key.
    """
    if kind not in PlatformActivityEvent.Kind.values:
        raise ValueError("Unsupported platform activity kind")
    if dedupe_key is not None and (not isinstance(dedupe_key, str) or not 1 <= len(dedupe_key) <= 120):
        raise ValueError("Invalid event dedupe key")
    values = {"salon": salon, "kind": kind, "occurred_at": occurred_at or timezone.now(), "count": 1}
    if dedupe_key:
        event, created = PlatformActivityEvent.objects.get_or_create(
            dedupe_key=dedupe_key, defaults=values,
        )
        if not created and (event.salon_id != salon.pk or event.kind != kind):
            raise ValueError("Event dedupe key already belongs to another operation")
        return event, created
    return PlatformActivityEvent.objects.create(**values), True


def usage_summary(*, since, until=None):
    """Counts of events and distinct participating salons in [since, until)."""
    until = until or timezone.now()
    if since >= until:
        raise ValueError("Invalid reporting interval")
    qs = PlatformActivityEvent.objects.filter(occurred_at__gte=since, occurred_at__lt=until)
    return {
        "events": qs.aggregate(total=Sum("count"))["total"] or 0,
        "active_salons": qs.values("salon_id").distinct().count(),
        "by_kind": list(qs.values("kind").annotate(total=Sum("count"), salons=Count("salon_id", distinct=True)).order_by("kind")),
    }


def activity_retention(*, cohort_start, cohort_end, return_start, return_end):
    """Cohort retention: salons active in first window and again in second.

    This is usage retention, NOT paid subscription renewal. No new salons are
    added to the denominator after cohort_end.
    """
    if not (cohort_start < cohort_end <= return_start < return_end):
        raise ValueError("Reporting windows must be ordered and non-overlapping")
    cohort = PlatformActivityEvent.objects.filter(
        occurred_at__gte=cohort_start, occurred_at__lt=cohort_end,
    ).values_list("salon_id", flat=True).distinct()
    cohort_size = cohort.count()
    retained = PlatformActivityEvent.objects.filter(
        salon_id__in=cohort, occurred_at__gte=return_start, occurred_at__lt=return_end,
    ).values("salon_id").distinct().count()
    return {
        "cohort_salons": cohort_size,
        "retained_salons": retained,
        "retention_percent": round(100 * retained / cohort_size, 1) if cohort_size else None,
    }
