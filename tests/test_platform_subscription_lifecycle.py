"""Subscription lifecycle transitions must be auditable and idempotent."""
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.platform_admin.models import SalonSubscription, SubscriptionChangeLog, SubscriptionPlan
from apps.platform_admin.subscription_lifecycle import change_subscription


@pytest.mark.django_db
def test_change_subscription_records_once_and_never_creates_payment(salon):
    from apps.finance.models import Payment

    now = timezone.now()
    plan = SubscriptionPlan.objects.create(code="transition-test", name="آزمون", period_days=30)
    subscription = SalonSubscription.objects.create(
        salon=salon, plan=plan, status=SalonSubscription.Status.ACTIVE,
        starts_at=now - timedelta(days=2), ends_at=now + timedelta(days=28),
    )
    payment_count = Payment.objects.count()
    target = now + timedelta(days=40)
    updated, changed = change_subscription(
        subscription_id=subscription.pk, new_status=SalonSubscription.Status.ACTIVE,
        new_ends_at=target, reason="اصلاح تاریخ اعتبار توسط مدیر",
    )
    assert changed
    assert updated.ends_at == target
    assert SubscriptionChangeLog.objects.filter(subscription=subscription).count() == 1
    _, changed = change_subscription(
        subscription_id=subscription.pk, new_status=SalonSubscription.Status.ACTIVE,
        new_ends_at=target, reason="تلاش تکراری برای اصلاح",
    )
    assert not changed
    assert SubscriptionChangeLog.objects.filter(subscription=subscription).count() == 1
    assert Payment.objects.count() == payment_count


@pytest.mark.django_db
def test_invalid_transition_does_not_mutate_subscription(salon):
    now = timezone.now()
    plan = SubscriptionPlan.objects.create(code="invalid-transition", name="آزمون", period_days=30)
    subscription = SalonSubscription.objects.create(
        salon=salon, plan=plan, status=SalonSubscription.Status.ACTIVE,
        starts_at=now, ends_at=now + timedelta(days=30),
    )
    with pytest.raises(ValidationError):
        change_subscription(
            subscription_id=subscription.pk, new_status="unknown",
            new_ends_at=now + timedelta(days=31), reason="تغییر اشتباه اشتراک",
        )
    subscription.refresh_from_db()
    assert subscription.status == SalonSubscription.Status.ACTIVE
    assert not SubscriptionChangeLog.objects.filter(subscription=subscription).exists()
