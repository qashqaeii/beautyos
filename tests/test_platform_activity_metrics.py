"""Phase 1 product analytics: privacy, idempotency and cohort semantics."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.platform_admin.activity_metrics import activity_retention, record_activity, usage_summary
from apps.platform_admin.models import PlatformActivityEvent


@pytest.mark.django_db
def test_event_deduplication_and_allowlist(salon):
    kind = PlatformActivityEvent.Kind.APPOINTMENT_CREATED
    first, created = record_activity(salon=salon, kind=kind, dedupe_key="appointment-created:fixture-1")
    assert created
    again, created = record_activity(salon=salon, kind=kind, dedupe_key="appointment-created:fixture-1")
    assert not created
    assert first.pk == again.pk
    assert PlatformActivityEvent.objects.count() == 1
    with pytest.raises(ValueError):
        record_activity(salon=salon, kind="phone_number_uploaded")


@pytest.mark.django_db
def test_usage_summary_and_retention_excludes_new_salons(salon):
    now = timezone.now()
    kind = PlatformActivityEvent.Kind.CUSTOMER_CREATED
    record_activity(salon=salon, kind=kind, occurred_at=now-timedelta(days=20))
    record_activity(salon=salon, kind=kind, occurred_at=now-timedelta(days=2))
    report = usage_summary(since=now-timedelta(days=30), until=now)
    assert report["events"] == 2
    assert report["active_salons"] == 1
    retained = activity_retention(
        cohort_start=now-timedelta(days=30),
        cohort_end=now-timedelta(days=15),
        return_start=now-timedelta(days=7),
        return_end=now,
    )
    assert retained == {"cohort_salons": 1, "retained_salons": 1, "retention_percent": 100.0}


@pytest.mark.django_db
def test_empty_cohort_does_not_claim_perfect_retention():
    now = timezone.now()
    result = activity_retention(
        cohort_start=now-timedelta(days=60), cohort_end=now-timedelta(days=50),
        return_start=now-timedelta(days=30), return_end=now-timedelta(days=20),
    )
    assert result["retention_percent"] is None
