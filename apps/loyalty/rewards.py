"""Internal gifts and service rewards; never implicitly mutate financial invoices."""
from uuid import UUID

import jdatetime
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.loyalty.automation import active_policy, grant_source
from apps.loyalty.models import LoyaltyAccount, LoyaltyAward, LoyaltyReward, LoyaltyTransaction, RewardRedemption, _refresh_tier_after_balance_change


def _audit(salon, actor, obj, message, action=AuditLog.Action.CREATE):
    AuditLog.objects.create(salon=salon,actor=actor,action=action,entity_type="loyalty_redemption",
        entity_id=str(obj.pk),message=message,metadata={"points":obj.points_cost})


def _uuid(value):
    try:
        return UUID(str(value))
    except (ValueError,TypeError,AttributeError):
        raise ValidationError("شناسه درخواست معتبر نیست.") from None


@transaction.atomic
def redeem_reward(*, salon, account_id, reward_id, request_key, actor):
    key=_uuid(request_key)
    account=LoyaltyAccount.scoped(salon).select_for_update().filter(pk=account_id,customer__salon=salon,customer__is_deleted=False).first()
    if account is None:
        raise ValidationError("عضو باشگاه معتبر نیست.")
    def check(row):
        if (row.account_id,row.reward_id)!=(account_id,reward_id):
            raise ValidationError("درخواست قبلاً با اطلاعات دیگری ثبت شده است.")
        return row
    previous=RewardRedemption.scoped(salon).filter(request_key=key).first()
    if previous:
        return check(previous)
    reward=LoyaltyReward.scoped(salon).select_for_update().filter(pk=reward_id,is_active=True).first()
    if reward is None:
        raise ValidationError("پاداش در دسترس نیست.")
    if account.points_balance<reward.points_cost:
        raise ValidationError("امتیاز مشتری کافی نیست.")
    try:
        with transaction.atomic():
            row,created=RewardRedemption.objects.get_or_create(salon=salon,request_key=key,defaults={
                "account":account,"reward":reward,"title_snapshot":reward.title,"points_cost":reward.points_cost})
    except IntegrityError as exc:
        raise ValidationError("درخواست تکراری است.") from exc
    if not created:
        return check(row)
    account.points_balance-=row.points_cost
    account.save(update_fields=["points_balance","updated_at"])
    _refresh_tier_after_balance_change(account)
    LoyaltyTransaction.objects.create(salon=salon,account=account,kind=LoyaltyTransaction.Kind.REDEEM,
        points=row.points_cost,reference=f"reward:{row.pk}",note=f"پاداش: {row.title_snapshot}")
    _audit(salon,actor,row,"ثبت مصرف امتیاز")
    return row


@transaction.atomic
def change_redemption(*,salon,redemption_id,status,actor):
    if status not in ("fulfilled","cancelled"):
        raise ValidationError("عملیات معتبر نیست.")
    initial=RewardRedemption.scoped(salon).filter(pk=redemption_id).first()
    if initial is None:
        raise ValidationError("پاداش یافت نشد.")
    account=LoyaltyAccount.scoped(salon).select_for_update().get(pk=initial.account_id)
    row=RewardRedemption.scoped(salon).select_for_update().get(pk=initial.pk)
    if row.status==status:
        return row
    if row.status!="pending":
        raise ValidationError("فقط پاداش در انتظار قابل تغییر است.")
    row.status=status
    if status=="cancelled":
        account.points_balance+=row.points_cost
        account.save(update_fields=["points_balance","updated_at"])
        _refresh_tier_after_balance_change(account)
        LoyaltyTransaction.objects.create(salon=salon,account=account,kind=LoyaltyTransaction.Kind.ADJUST,
            points=row.points_cost,reference=str(row.points_cost),note=f"بازگشت امتیاز پاداش {row.pk}")
    row.save(update_fields=["status","updated_at"])
    _audit(salon,actor,row,"تحویل پاداش" if status=="fulfilled" else "لغو پاداش و بازگشت امتیاز",AuditLog.Action.UPDATE)
    return row


def birthday_month(customer, today=None):
    if not customer.birth_date:
        return False
    current=jdatetime.date.fromgregorian(date=today or timezone.localdate())
    birth=jdatetime.date.fromgregorian(date=customer.birth_date)
    return birth.month==current.month


def birthday_source_key(customer, today=None):
    year=jdatetime.date.fromgregorian(date=today or timezone.localdate()).year
    return f"{customer.pk}:{year}"


def claim_birthday(*,salon,customer,actor):
    policy=active_policy(salon)
    if customer.salon_id!=salon.pk or customer.is_deleted or not birthday_month(customer):
        raise ValidationError("مشتری در ماه تولد شمسی نیست.")
    key=birthday_source_key(customer)
    previous=LoyaltyAward.scoped(salon).filter(source_kind="birthday",source_key=key).first()
    if previous:
        return previous
    if not policy or not policy.birthday_points:
        raise ValidationError("هدیه تولد در تنظیمات باشگاه فعال نیست.")
    return grant_source(salon=salon,customer=customer,kind="birthday",key=key,points=policy.birthday_points,
        note="هدیه تولد سالانه",actor=actor)
