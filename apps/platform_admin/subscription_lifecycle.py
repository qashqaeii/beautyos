"""Explicit, transaction-safe subscription transitions.

No gateway integration, charges, or entitlement updates happen here.
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.platform_admin.models import SalonSubscription, SubscriptionChangeLog


@transaction.atomic
def change_subscription(*, subscription_id, new_status, new_ends_at, reason, actor=None, source="operator"):
    if new_status not in SalonSubscription.Status.values:
        raise ValidationError("وضعیت اشتراک معتبر نیست.")
    if not isinstance(reason, str) or len(reason.strip()) < 8 or len(reason) > 300:
        raise ValidationError("دلیل تغییر باید بین ۸ تا ۳۰۰ نویسه باشد.")
    if source not in ("operator", "system", "verified_provider"):
        raise ValidationError("منبع تغییر نامعتبر است.")
    subscription = SalonSubscription.objects.select_for_update().get(pk=subscription_id)
    if new_ends_at is None or new_ends_at <= subscription.starts_at:
        raise ValidationError("تاریخ پایان باید بعد از شروع دوره باشد.")
    if subscription.trial_ends_at and new_ends_at < subscription.trial_ends_at:
        raise ValidationError("تاریخ پایان نمی‌تواند قبل از پایان آزمایشی باشد.")
    if subscription.status == new_status and subscription.ends_at == new_ends_at:
        return subscription, False
    old_status, old_end = subscription.status, subscription.ends_at
    subscription.status = new_status
    subscription.ends_at = new_ends_at
    subscription.full_clean()
    subscription.save(update_fields=["status", "ends_at", "updated_at"])
    SubscriptionChangeLog.objects.create(
        subscription=subscription, actor=actor, old_status=old_status,
        new_status=new_status, old_ends_at=old_end, new_ends_at=new_ends_at,
        reason=reason.strip(), source=source,
    )
    return subscription, True
