"""Atomic purchase-session application and auditable reversal for salon visits."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.packages.models import CustomerPackage, PackageSessionUse


@transaction.atomic
def consume_package_session(customer_package: CustomerPackage, appointment, *, actor=None) -> PackageSessionUse:
    from apps.appointments.models import Appointment
    from apps.finance.ledger import payment_refunded
    from apps.finance.models import InvoiceLine, Payment
    from apps.audit.models import AuditLog

    # Same appointment-first lock ordering as checkout, refunds and cancellations.
    appointment = Appointment.scoped(appointment.salon).select_for_update().get(pk=appointment.pk)
    customer_package = CustomerPackage.scoped(appointment.salon).select_for_update().filter(
        pk=customer_package.pk,
    ).first()
    if customer_package is None or customer_package.customer_id != appointment.customer_id:
        raise ValidationError("پکیج متعلق به مشتری یا سالن این نوبت نیست.")
    if appointment.status != Appointment.Status.COMPLETED:
        raise ValidationError("جلسه پکیج فقط برای مراجعه تکمیل‌شده قابل استفاده است.")
    if customer_package.sessions_remaining <= 0:
        raise ValidationError("جلسات پکیج تمام شده است.")
    if customer_package.expires_at <= timezone.now():
        raise ValidationError("اعتبار پکیج منقضی شده است.")
    if InvoiceLine.objects.filter(salon=appointment.salon, appointment=appointment).exists():
        raise ValidationError("برای این نوبت فاکتور صادر شده است.")
    if PackageSessionUse.scoped(appointment.salon).filter(appointment=appointment).exists():
        raise ValidationError("برای این نوبت قبلاً جلسه پکیج ثبت شده است.")
    payments = Payment.scoped(appointment.salon).filter(
        appointment=appointment,
    ).prefetch_related("refunds")
    if any(
        int(payment.discount_toman) > 0
        or max(0, int(payment.paid_amount_toman) - payment_refunded(payment)) > 0
        for payment in payments
    ):
        raise ValidationError("برای این خدمت دریافت یا تخفیف ثبت شده است؛ ابتدا تسویه مالی آن را بررسی کنید.")

    customer_package.sessions_used += 1
    customer_package.save(update_fields=["sessions_used", "updated_at"])
    use = PackageSessionUse.objects.create(
        salon=customer_package.salon,
        customer_package=customer_package,
        appointment=appointment,
    )
    AuditLog.objects.create(
        salon=appointment.salon, actor=actor, action=AuditLog.Action.CREATE,
        entity_type="package_session_use", entity_id=str(use.pk),
        message="مصرف جلسه پکیج برای خدمت تکمیل‌شده",
        metadata={"appointment_id": appointment.pk, "customer_package_id": customer_package.pk},
    )
    return use


@transaction.atomic
def reverse_package_session(*, appointment, actor=None):
    """Restore an already consumed session when its completed visit is cancelled.

    Keep the use row with reversed_at for a traceable accounting history.
    Idempotent by appointment and serialized with the same lock ordering.
    """
    from apps.appointments.models import Appointment
    from apps.audit.models import AuditLog

    appointment = Appointment.scoped(appointment.salon).select_for_update().get(pk=appointment.pk)
    use = PackageSessionUse.scoped(appointment.salon).select_for_update().filter(
        appointment=appointment, reversed_at__isnull=True,
    ).first()
    if use is None:
        return None
    purchase = CustomerPackage.scoped(appointment.salon).select_for_update().get(
        pk=use.customer_package_id,
    )
    if purchase.sessions_used <= 0:
        raise ValidationError("تعداد جلسات مصرف‌شده پکیج ناسازگار است؛ ابتدا حساب را بررسی کنید.")
    purchase.sessions_used -= 1
    purchase.save(update_fields=["sessions_used", "updated_at"])
    use.reversed_at = timezone.now()
    use.save(update_fields=["reversed_at", "updated_at"])
    AuditLog.objects.create(
        salon=appointment.salon, actor=actor, action=AuditLog.Action.UPDATE,
        entity_type="package_session_reversal", entity_id=str(use.pk),
        message="بازگردانی جلسه پکیج پس از لغو مراجعه",
        metadata={"appointment_id": appointment.pk, "customer_package_id": purchase.pk},
    )
    return use
