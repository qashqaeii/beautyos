"""No configured gateway means no subscription can be paid or extended."""
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError

from apps.platform_admin.models import (
    PlatformSubscriptionOrder, SalonSubscription, SubscriptionPlan,
)
from apps.platform_admin.subscription_settlement import settle_from_gateway


@pytest.mark.django_db
def test_unconfigured_gateway_fails_closed(salon):
    plan = SubscriptionPlan.objects.create(
        code="gateway-guard", name="پلن", price_toman=100000,
        period_days=30, is_active=True,
    )
    order = PlatformSubscriptionOrder.objects.create(
        salon=salon, plan=plan, request_key=uuid4(),
        amount_toman=100000, period_days=30,
    )
    with pytest.raises(ValidationError):
        settle_from_gateway(order_id=order.pk, provider="unconfigured")
    order.refresh_from_db()
    assert order.status == PlatformSubscriptionOrder.Status.PENDING
    assert not SalonSubscription.objects.filter(salon=salon).exists()
