"""Create pending SaaS orders without ever granting access or recording revenue."""
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.platform_admin.models import PlatformSubscriptionOrder, SubscriptionPlan


@transaction.atomic
def create_pending_order(*, salon, plan_id, request_key):
    try:
        request_key = UUID(str(request_key))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationError("شناسه درخواست معتبر نیست.") from exc

    existing = PlatformSubscriptionOrder.objects.select_for_update().filter(
        request_key=request_key,
    ).first()
    if existing is not None:
        if existing.salon_id != salon.pk or existing.plan_id != plan_id:
            raise ValidationError("شناسه درخواست برای سفارش دیگری استفاده شده است.")
        return existing, False

    plan = SubscriptionPlan.objects.get(pk=plan_id)
    if not plan.is_active or plan.period_days < 1 or plan.price_toman <= 0:
        raise ValidationError("پلن قابل خرید نیست.")

    # Snapshot pricing protects old orders from later plan edits.
    try:
        with transaction.atomic():
            return PlatformSubscriptionOrder.objects.create(
                salon=salon, plan=plan, request_key=request_key,
                amount_toman=plan.price_toman, period_days=plan.period_days,
                status=PlatformSubscriptionOrder.Status.PENDING,
            ), True
    except IntegrityError:
        # A concurrent retry can race on request_key.
        existing = PlatformSubscriptionOrder.objects.get(request_key=request_key)
        if existing.salon_id != salon.pk or existing.plan_id != plan_id:
            raise ValidationError("شناسه درخواست برای سفارش دیگری استفاده شده است.")
        return existing, False
