"""Order creation is retry-safe and never counts as a verified payment."""
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError

from apps.platform_admin.models import PlatformSubscriptionOrder, SubscriptionPlan
from apps.platform_admin.subscription_orders import create_pending_order


@pytest.mark.django_db
def test_pending_order_is_idempotent_and_price_is_snapshotted(salon):
    plan = SubscriptionPlan.objects.create(
        code="order-test", name="پلن پایه", price_toman=900000,
        period_days=30, is_active=True,
    )
    key = uuid4()
    first, created = create_pending_order(salon=salon, plan_id=plan.pk, request_key=key)
    assert created
    assert first.amount_toman == 900000
    assert first.status == PlatformSubscriptionOrder.Status.PENDING
    plan.price_toman = 1200000
    plan.save(update_fields=["price_toman"])
    second, created = create_pending_order(salon=salon, plan_id=plan.pk, request_key=key)
    assert not created
    assert second.pk == first.pk
    assert second.amount_toman == 900000
    assert PlatformSubscriptionOrder.objects.count() == 1
    assert not hasattr(first, "payment")


@pytest.mark.django_db
def test_pending_order_rejects_inactive_plan(salon):
    plan = SubscriptionPlan.objects.create(
        code="order-inactive", name="غیرفعال", price_toman=100,
        period_days=30, is_active=False,
    )
    with pytest.raises(ValidationError):
        create_pending_order(salon=salon, plan_id=plan.pk, request_key=uuid4())
    assert PlatformSubscriptionOrder.objects.count() == 0
