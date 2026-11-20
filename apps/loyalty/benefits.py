"""Salon-local referrals and one-use customer vouchers."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.loyalty.automation import active_policy, grant_source, _reduce_source
from apps.loyalty.models import Referral, LoyaltyVoucher


@transaction.atomic
def register_referral(*, salon, referrer_id, referred_id, actor):
    if referrer_id == referred_id:
        raise ValidationError("معرف و مشتری جدید باید متفاوت باشند.")
    customers={c.pk:c for c in Customer.scoped(salon).select_for_update().filter(pk__in=[referrer_id,referred_id],is_deleted=False).order_by("pk")}
    if len(customers)!=2:
        raise ValidationError("مشتریان معتبر نیستند.")
    previous=Referral.scoped(salon).filter(referred_id=referred_id).first()
    if previous:
        if previous.referrer_id==referrer_id:return previous
        raise ValidationError("این مشتری قبلاً معرف دارد.")
    policy=active_policy(salon)
    if not policy or not policy.referral_points:
        raise ValidationError("پاداش معرفی در تنظیمات باشگاه فعال نیست.")
    if Appointment.scoped(salon).filter(customer_id=referred_id,status=Appointment.Status.COMPLETED).exists():
        raise ValidationError("معرف باید پیش از اولین مراجعه انجام‌شده ثبت شود.")
    # Referrer must be an existing customer with a completed visit; no mutual self-referrals.
    if not Appointment.scoped(salon).filter(customer_id=referrer_id,status=Appointment.Status.COMPLETED).exists():
        raise ValidationError("معرف باید حداقل یک مراجعه انجام‌شده داشته باشد.")
    row=Referral.objects.create(salon=salon,referrer_id=referrer_id,referred_id=referred_id,points_snapshot=policy.referral_points)
    AuditLog.objects.create(salon=salon,actor=actor,action=AuditLog.Action.CREATE,entity_type="loyalty_referral",entity_id=str(row.pk),message="ثبت معرفی مشتری")
    return row


def award_referral(appointment):
    # Caller locks appointment. Lock referred customer to serialize with registration.
    Customer.scoped(appointment.salon).select_for_update().get(pk=appointment.customer_id)
    row=Referral.scoped(appointment.salon).select_for_update().filter(referred_id=appointment.customer_id,status="pending").first()
    if not row or appointment.status!=Appointment.Status.COMPLETED or not active_policy(appointment.salon):
        return None
    grant=grant_source(salon=appointment.salon,customer=row.referrer,kind="referral",key=row.pk,points=row.points_snapshot,note=f"پاداش معرفی مشتری {row.referred_id}")
    if not grant:return None
    row.qualifying_visit=appointment
    row.status="awarded"
    row.save(update_fields=["qualifying_visit","status","updated_at"])
    return row


def reverse_referral(appointment):
    row=Referral.scoped(appointment.salon).select_for_update().filter(qualifying_visit=appointment,status="awarded").first()
    if row:
        _reduce_source(salon=appointment.salon,kind="referral",key=row.pk,target=lambda award:0,note="برگشت پاداش معرفی به دلیل لغو مراجعه")
        row.status="reversed"
        row.save(update_fields=["status","updated_at"])


def available_vouchers(salon,customer):
    return LoyaltyVoucher.scoped(salon).filter(customer=customer,is_active=True,invoice__isnull=True,expires_on__gte=timezone.localdate()).order_by("expires_on","pk")


def lock_voucher(*, salon, customer, voucher_id):
    voucher=available_vouchers(salon,customer).select_for_update().filter(pk=voucher_id).first()
    if not voucher:
        raise ValidationError("اعتبار تخفیف نامعتبر، مصرف‌شده یا منقضی است.")
    return voucher
