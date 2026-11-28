"""Subscription reporting stays independent of billing and salon receipts."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.platform_admin.subscription_health import subscription_health
from apps.platform_admin.models import SalonSubscription, SubscriptionPlan


@pytest.mark.django_db
def test_subscription_health_empty_and_invalid_horizon():
    result = subscription_health()
    assert result["valid_active"] == 0
    assert result["expiring_soon"] == 0
    assert result["expired_dates_unreconciled"] == 0
    with pytest.raises(ValueError):
        subscription_health(horizon_days=0)


@pytest.mark.django_db
def test_subscription_health_does_not_count_expired_active_as_valid(salon):
    now = timezone.now()
    plan = SubscriptionPlan.objects.create(
        code="health-test", name="پلن آزمون", period_days=30,
    )
    SalonSubscription.objects.create(
        salon=salon, plan=plan, status=SalonSubscription.Status.ACTIVE,
        starts_at=now - timedelta(days=31), ends_at=now - timedelta(days=1),
    )
    result = subscription_health(now=now)
    assert result["valid_active"] == 0
    assert result["expired_dates_unreconciled"] == 1
    assert result["expiring_soon"] == 0
