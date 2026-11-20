"""Idempotent source-linked awards; invoked inside existing domain transactions."""
from django.db import transaction
from django.db.models import Sum

from apps.loyalty.models import LoyaltyAccount, LoyaltyAward, LoyaltyPolicy, LoyaltyTransaction, _refresh_tier_after_balance_change

MAX_EVENT_POINTS = 1000000


def active_policy(salon):
    return LoyaltyPolicy.scoped(salon).filter(enabled=True).first()


def _write_delta(account, delta, reference, note):
    if not delta:
        return
    account.points_balance += delta
    account.save(update_fields=["points_balance", "updated_at"])
    _refresh_tier_after_balance_change(account)
    LoyaltyTransaction.objects.create(salon_id=account.salon_id, account=account,
        kind=LoyaltyTransaction.Kind.EARN if delta > 0 else LoyaltyTransaction.Kind.ADJUST,
        points=abs(delta), reference=reference if delta>0 else str(delta), note=note)


@transaction.atomic
def grant_source(*, salon, customer, kind, key, points, unit=0, note):
    if customer.salon_id != salon.pk or customer.is_deleted:
        return None
    points = min(MAX_EVENT_POINTS, max(0, int(points)))
    if not points:
        return None
    account, _ = LoyaltyAccount.objects.select_for_update().get_or_create(salon=salon, customer=customer)
    award, created = LoyaltyAward.objects.get_or_create(salon=salon, source_kind=kind, source_key=str(key),
        defaults={"account":account,"original_points":points,"remaining_points":points,"spend_unit_toman":unit})
    if created:
        _write_delta(account, points, f"{kind}:{key}"[:64], note)
    return award


@transaction.atomic
def _reduce_source(*, salon, kind, key, target, note):
    award = LoyaltyAward.scoped(salon).filter(source_kind=kind, source_key=str(key)).first()
    if not award:
        return None
    # The same account lock serializes all earning, redeeming and reversal events.
    account = LoyaltyAccount.scoped(salon).select_for_update().get(pk=award.account_id)
    award = LoyaltyAward.scoped(salon).select_for_update().get(pk=award.pk)
    remaining = max(0, min(award.remaining_points, int(target(award))))
    delta = remaining - award.remaining_points
    if delta:
        # Points already redeemed become a negative balance, offset by future earnings.
        # Financial refunds must not fail because a customer has spent their points.
        _write_delta(account, delta, "", note)
        award.remaining_points = remaining
        award.save(update_fields=["remaining_points", "updated_at"])
    return award


def award_payment(payment):
    from apps.finance.models import Payment
    if payment.status not in (Payment.Status.PAID, Payment.Status.PARTIAL) or payment.paid_amount_toman <= 0:
        return None
    policy = active_policy(payment.salon)
    if not policy:
        return None
    unit = policy.spend_per_point_toman
    return grant_source(salon=payment.salon, customer=payment.customer, kind="payment", key=payment.pk,
        points=payment.paid_amount_toman // unit, unit=unit, note=f"امتیاز دریافت شماره {payment.pk}")


def reconcile_refund(payment):
    from apps.finance.models import Refund
    refunded = Refund.scoped(payment.salon).filter(payment=payment).aggregate(total=Sum("amount_toman"))["total"] or 0
    net = max(0, payment.paid_amount_toman - refunded)
    return _reduce_source(salon=payment.salon, kind="payment", key=payment.pk,
        target=lambda award: net // max(1, award.spend_unit_toman), note=f"اصلاح امتیاز استرداد دریافت {payment.pk}")


def award_visit(appointment):
    from apps.appointments.models import Appointment
    if appointment.status != Appointment.Status.COMPLETED:
        return None
    policy = active_policy(appointment.salon)
    if not policy:
        return None
    return grant_source(salon=appointment.salon, customer=appointment.customer, kind="visit", key=appointment.pk,
        points=policy.visit_points, note=f"امتیاز مراجعه انجام‌شده {appointment.pk}")


def reverse_visit(appointment):
    return _reduce_source(salon=appointment.salon, kind="visit", key=appointment.pk,
        target=lambda award: 0, note=f"اصلاح امتیاز نوبت لغوشده {appointment.pk}")
