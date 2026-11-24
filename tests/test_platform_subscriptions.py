"""Phase 6 subscription foundation: no salon cash flow or forced entitlement changes."""
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.platform_admin.models import SalonSubscription, SubscriptionPlan
from apps.salons.models import Salon
from tests.test_platform_admin import platform_operator, platform_client  # noqa: F401


@pytest.mark.django_db
def test_subscription_inventory_restricted_to_platform_superusers(client, owner_membership, platform_operator):
    url = reverse("platform_admin:subscriptions")
    assert client.get(url).status_code == 302
    client.force_login(owner_membership.user)
    assert client.get(url).status_code == 403
    client.force_login(platform_operator)
    response = client.get(url)
    assert response.status_code == 200
    assert "اشتراک‌ها و پلن‌ها" in response.content.decode()
    assert response.context["unassigned_count"] == Salon.objects.count()


@pytest.mark.django_db
def test_subscription_models_are_independent_from_salon_payment_ledger(
    platform_client, salon, salon_b,
):
    from apps.finance.models import Payment
    starting_payments = Payment.objects.count()
    now = timezone.now()
    plan = SubscriptionPlan.objects.create(
        code="monthly", name="ماهانه", price_toman=750000,
        period_days=30, trial_days=7, is_active=True,
    )
    subscription = SalonSubscription(
        salon=salon, plan=plan, status=SalonSubscription.Status.TRIAL,
        starts_at=now, trial_ends_at=now + timedelta(days=7),
        ends_at=now + timedelta(days=30),
    )
    subscription.full_clean()
    subscription.save()
    assert Payment.objects.count() == starting_payments
    assert salon_b.pk != subscription.salon_id
    response = platform_client.get(reverse("platform_admin:subscriptions"))
    assert response.status_code == 200
    assert plan.name in response.content.decode()
    assert salon.name in response.content.decode()
    assert response.context["unassigned_count"] == Salon.objects.count() - 1
    assert subscription.status == SalonSubscription.Status.TRIAL


@pytest.mark.django_db
def test_subscription_cannot_have_invalid_interval_or_missing_trial_end(salon):
    now = timezone.now()
    plan = SubscriptionPlan.objects.create(code="starter", name="شروع", period_days=30)
    instance = SalonSubscription(
        salon=salon, plan=plan, status=SalonSubscription.Status.TRIAL,
        starts_at=now, ends_at=now,
    )
    with pytest.raises(ValidationError):
        instance.full_clean()
    instance.ends_at = now + timedelta(days=30)
    with pytest.raises(ValidationError):
        instance.full_clean()
    instance.trial_ends_at = now + timedelta(days=31)
    with pytest.raises(ValidationError):
        instance.full_clean()
    instance.trial_ends_at = now + timedelta(days=7)
    instance.full_clean()


@pytest.mark.django_db
def test_one_subscription_per_salon(salon):
    from django.db import IntegrityError, transaction
    now = timezone.now()
    plan = SubscriptionPlan.objects.create(code="basic", name="پایه")
    SalonSubscription.objects.create(
        salon=salon, plan=plan, status=SalonSubscription.Status.ACTIVE,
        starts_at=now, ends_at=now + timedelta(days=30),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SalonSubscription.objects.create(
                salon=salon, plan=plan, status=SalonSubscription.Status.ACTIVE,
                starts_at=now, ends_at=now + timedelta(days=30),
            )
    assert SalonSubscription.objects.count() == 1


@pytest.mark.django_db
def test_subscription_list_get_does_not_modify_subscription_state(platform_client, salon):
    now = timezone.now()
    plan = SubscriptionPlan.objects.create(code="periodic", name="فصلی", period_days=90)
    subscription = SalonSubscription.objects.create(
        salon=salon, plan=plan, status=SalonSubscription.Status.ACTIVE,
        starts_at=now - timedelta(days=100),
        ends_at=now - timedelta(days=10),
    )
    response = platform_client.get(reverse("platform_admin:subscriptions"), {"status": "active"})
    assert response.status_code == 200
    subscription.refresh_from_db()
    assert subscription.status == SalonSubscription.Status.ACTIVE
