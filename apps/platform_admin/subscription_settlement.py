"""Trusted payment settlement boundary for BeautyOS subscriptions.

Only a server-side gateway adapter may call this with a verified result.
No browser callback, query string or operator form is proof of payment.
"""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.platform_admin.models import (
    PlatformSubscriptionOrder, SalonSubscription, SubscriptionChangeLog,
)


@transaction.atomic
def settle_verified_order(*, order_id, verifier):
    """Verify with a trusted provider, then atomically settle and extend once.

    verifier(order) must perform server-to-server verification and return a dict
    containing verified=True, provider, reference, amount_toman and order_id.
    Never pass untrusted callback parameters directly as the verifier result.
    """
    if not callable(verifier):
        raise ValidationError("سرویس تأیید پرداخت در دسترس نیست.")
    order = PlatformSubscriptionOrder.objects.select_for_update().select_related(
        "plan", "salon",
    ).get(pk=order_id)
    if order.status == PlatformSubscriptionOrder.Status.VERIFIED:
        return order, False
    if order.status != PlatformSubscriptionOrder.Status.PENDING:
        raise ValidationError("سفارش قابل تسویه نیست.")
    proof = verifier(order)
    if not isinstance(proof, dict) or proof.get("verified") is not True:
        raise ValidationError("تأیید معتبر از درگاه دریافت نشد.")
    provider, reference = proof.get("provider"), proof.get("reference")
    if (not isinstance(provider, str) or not 1 <= len(provider) <= 40
            or not isinstance(reference, str) or not 1 <= len(reference) <= 120
            or proof.get("order_id") != order.pk
            or type(proof.get("amount_toman")) is not int
            or proof["amount_toman"] != order.amount_toman):
        raise ValidationError("مشخصات تراکنش با سفارش مطابقت ندارد.")
    if PlatformSubscriptionOrder.objects.filter(
        status=PlatformSubscriptionOrder.Status.VERIFIED,
        provider=provider, provider_reference=reference,
    ).exclude(pk=order.pk).exists():
        raise ValidationError("شناسه تراکنش قبلاً برای سفارش دیگری ثبت شده است.")

    now = timezone.now()
    subscription = SalonSubscription.objects.select_for_update().filter(
        salon_id=order.salon_id,
    ).first()
    if subscription is None:
        subscription = SalonSubscription.objects.create(
            salon=order.salon, plan=order.plan,
            status=SalonSubscription.Status.ACTIVE,
            starts_at=now, ends_at=now + timedelta(days=order.period_days),
        )
        old_status, old_end = "", None
    else:
        old_status, old_end = subscription.status, subscription.ends_at
        base = max(now, subscription.ends_at)
        subscription.ends_at = base + timedelta(days=order.period_days)
        subscription.status = SalonSubscription.Status.ACTIVE
        subscription.plan = order.plan
        subscription.canceled_at = None
        subscription.full_clean()
        subscription.save(update_fields=[
            "ends_at", "status", "plan", "canceled_at", "updated_at",
        ])
    order.status = PlatformSubscriptionOrder.Status.VERIFIED
    order.provider = provider
    order.provider_reference = reference
    order.verified_at = now
    order.save(update_fields=[
        "status", "provider", "provider_reference", "verified_at", "updated_at",
    ])
    SubscriptionChangeLog.objects.create(
        subscription=subscription, old_status=old_status,
        new_status=SalonSubscription.Status.ACTIVE,
        old_ends_at=old_end, new_ends_at=subscription.ends_at,
        reason=f"تسویه سفارش اشتراک شماره {order.pk}",
        source="verified_provider",
    )
    return order, True
