"""Platform subscription corrections cannot activate or extend subscriptions."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.platform_admin.models import SalonSubscription, SubscriptionPlan, SubscriptionChangeLog


@pytest.mark.django_db
def test_correction_requires_platform_superuser(client, salon):
    now = timezone.now()
    plan = SubscriptionPlan.objects.create(code="correction-auth", name="آزمون", period_days=30)
    sub = SalonSubscription.objects.create(
        salon=salon, plan=plan, status=SalonSubscription.Status.ACTIVE,
        starts_at=now-timedelta(days=40), ends_at=now-timedelta(days=10),
    )
    url = reverse("platform_admin:subscription_correct", args=[sub.pk])
    assert client.post(url, {"status": "expired", "reason": "پایان اعتبار ثبت‌شده"}).status_code == 302
    sub.refresh_from_db()
    assert sub.status == SalonSubscription.Status.ACTIVE
    assert not SubscriptionChangeLog.objects.filter(subscription=sub).exists()


@pytest.mark.django_db
def test_correction_rejects_get(client, salon):
    now = timezone.now()
    plan = SubscriptionPlan.objects.create(code="correction-method", name="آزمون", period_days=30)
    sub = SalonSubscription.objects.create(
        salon=salon, plan=plan, status=SalonSubscription.Status.ACTIVE,
        starts_at=now-timedelta(days=40), ends_at=now-timedelta(days=1),
    )
    url = reverse("platform_admin:subscription_correct", args=[sub.pk])
    # Anonymous GET is blocked by the platform guard before reaching the view.
    assert client.get(url).status_code == 302
