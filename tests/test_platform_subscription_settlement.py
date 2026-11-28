"""Payment settlement must be server-verified, atomic and replay-safe."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.platform_admin.models import (
    PlatformSubscriptionOrder, SalonSubscription, SubscriptionChangeLog, SubscriptionPlan,
)
from apps.platform_admin.subscription_settlement import settle_verified_order


def verified_proof(order, reference="test-reference"):
    return {
        "verified": True, "provider": "test-provider",
        "reference": reference, "amount_toman": order.amount_toman,
        "order_id": order.pk,
    }


@pytest.fixture
def pending_order(salon):
    plan = SubscriptionPlan.objects.create(
        code="settlement-test", name="پلن آزمون",
        price_toman=350000, period_days=30, is_active=True,
    )
    return PlatformSubscriptionOrder.objects.create(
        salon=salon, plan=plan, request_key=uuid4(),
        amount_toman=350000, period_days=30,
    )


@pytest.mark.django_db
def test_verified_payment_activates_once(pending_order):
    order, changed = settle_verified_order(
        order_id=pending_order.pk, verifier=verified_proof,
    )
    assert changed
    assert order.status == PlatformSubscriptionOrder.Status.VERIFIED
    subscription = SalonSubscription.objects.get(salon=pending_order.salon)
    first_end = subscription.ends_at
    assert first_end > timezone.now() + timedelta(days=29)
    _, changed = settle_verified_order(
        order_id=pending_order.pk,
        verifier=lambda _: pytest.fail("Verified order must not reverify"),
    )
    assert not changed
    subscription.refresh_from_db()
    assert subscription.ends_at == first_end
    assert SubscriptionChangeLog.objects.filter(subscription=subscription).count() == 1


@pytest.mark.django_db
def test_invalid_proof_cannot_grant_subscription(pending_order):
    with pytest.raises(ValidationError):
        settle_verified_order(
            order_id=pending_order.pk,
            verifier=lambda order: {**verified_proof(order), "amount_toman": 1},
        )
    pending_order.refresh_from_db()
    assert pending_order.status == PlatformSubscriptionOrder.Status.PENDING
    assert not SalonSubscription.objects.filter(salon=pending_order.salon).exists()


@pytest.mark.django_db
def test_duplicate_provider_reference_cannot_extend_another_order(pending_order):
    settle_verified_order(order_id=pending_order.pk, verifier=verified_proof)
    second = PlatformSubscriptionOrder.objects.create(
        salon=pending_order.salon, plan=pending_order.plan,
        request_key=uuid4(), amount_toman=pending_order.amount_toman,
        period_days=pending_order.period_days,
    )
    before = SalonSubscription.objects.get(salon=pending_order.salon).ends_at
    with pytest.raises(ValidationError):
        settle_verified_order(order_id=second.pk, verifier=verified_proof)
    assert SalonSubscription.objects.get(salon=pending_order.salon).ends_at == before
    second.refresh_from_db()
    assert second.status == PlatformSubscriptionOrder.Status.PENDING
