"""Command center reporting contracts and access checks."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.platform_admin.command_center import command_center_snapshot
from apps.platform_admin.models import PlatformActivityEvent
from apps.platform_admin.activity_metrics import record_activity


@pytest.mark.django_db
def test_empty_command_center_never_invents_retention_or_revenue():
    result = command_center_snapshot(days=30)
    assert result["usage_active"] == 0
    assert result["retention"] is None
    assert result["cohort_size"] == 0
    assert result["prior_inactive"] == 0
    assert len(result["features"]) == len(PlatformActivityEvent.Kind.choices)
    with pytest.raises(ValueError):
        command_center_snapshot(days=999)


@pytest.mark.django_db
def test_command_center_tracks_fixed_cohort_and_no_activity(salon):
    now = timezone.now()
    record_activity(salon=salon, kind=PlatformActivityEvent.Kind.APPOINTMENT_CREATED,
                    occurred_at=now-timedelta(days=40))
    result = command_center_snapshot(days=30, now=now)
    assert result["usage_previous"] == 1
    assert result["usage_active"] == 0
    assert result["prior_inactive"] == 1
    assert result["retention"] == 0
    record_activity(salon=salon, kind=PlatformActivityEvent.Kind.APPOINTMENT_CREATED,
                    occurred_at=now-timedelta(days=1))
    result = command_center_snapshot(days=30, now=now)
    assert result["usage_active"] == 1
    assert result["retention"] == 100
    assert result["prior_inactive"] == 0


@pytest.mark.django_db
def test_central_overview_denies_anonymous(client):
    response = client.get(reverse("platform_admin:overview"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_trend_has_daily_zero_filled_points(salon):
    now = timezone.now()
    record_activity(
        salon=salon, kind=PlatformActivityEvent.Kind.CUSTOMER_CREATED,
        occurred_at=now - timedelta(days=2),
    )
    result = command_center_snapshot(days=7, now=now)
    assert len(result["trend"]) == 7
    assert sum(point["count"] for point in result["trend"]) == 1
    assert all(3 <= point["height"] <= 100 for point in result["trend"])
