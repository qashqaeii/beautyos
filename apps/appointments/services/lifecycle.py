from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.commissions.services import recognize_commission_for_appointment, reverse_commission_for_appointment
from apps.customers.services import refresh_customer_stats


class AppointmentLifecycleError(Exception):
    """User-facing appointment status transition failure."""


CANCELLED_CANNOT_COMPLETE_MSG = "نوبت لغوشده را نمی‌توان انجام‌شده ثبت کرد"


_COMPLETABLE = {
    Appointment.Status.CONFIRMED,
    Appointment.Status.CHECKED_IN,
}


def _locked_appointment(*, salon, appointment_id: int) -> Appointment:
    try:
        return (
            Appointment.scoped(salon)
            .select_for_update()
            .select_related("customer", "staff", "service")
            .get(pk=appointment_id)
        )
    except Appointment.DoesNotExist as exc:
        raise AppointmentLifecycleError("نوبت یافت نشد یا متعلق به این سالن نیست.") from exc


@transaction.atomic
def complete_appointment(*, salon, appointment_id: int) -> Appointment:
    appt = _locked_appointment(salon=salon, appointment_id=appointment_id)
    if appt.status == Appointment.Status.COMPLETED:
        return appt
    if appt.status == Appointment.Status.CANCELLED:
        raise AppointmentLifecycleError(CANCELLED_CANNOT_COMPLETE_MSG)
    if appt.status == Appointment.Status.PENDING:
        raise AppointmentLifecycleError("ابتدا رزرو را تأیید کنید، سپس مراجعه را تکمیل کنید.")
    if appt.status not in _COMPLETABLE:
        raise AppointmentLifecycleError("این نوبت در وضعیت قابل تکمیل نیست.")

    appt.status = Appointment.Status.COMPLETED
    appt.completed_at = timezone.now()
    appt.save(update_fields=["status", "completed_at", "updated_at"])
    recognize_commission_for_appointment(appt)
    from apps.loyalty.automation import award_visit
    # Serialize registration and first completion on the customer row.
    from apps.loyalty.benefits import award_referral
    award_referral(appt)
    award_visit(appt)
    refresh_customer_stats(appt.customer)
    return appt


@transaction.atomic
def cancel_appointment(*, salon, appointment_id: int) -> Appointment:
    appt = _locked_appointment(salon=salon, appointment_id=appointment_id)
    if appt.status == Appointment.Status.CANCELLED:
        return appt

    # A cancellation must not silently leave money collected for a
    # cancelled service or invalidate an immutable issued invoice.
    # Refund funds explicitly first; invoiced corrections require a
    # separate accounting adjustment instead of deleting history.
    from apps.finance.models import InvoiceLine, Payment
    from apps.finance.ledger import payment_refunded

    invoice_line = InvoiceLine.objects.filter(salon=salon, appointment=appt).first()
    payments = Payment.scoped(salon).filter(
        appointment=appt, paid_amount_toman__gt=0,
    ).exclude(status=Payment.Status.REFUNDED).prefetch_related("refunds")
    outstanding_receipts = sum(
        max(0, int(payment.paid_amount_toman) - payment_refunded(payment))
        for payment in payments
    )
    # Before delivery, a paid booking must be refunded before it is cancelled.
    # Completed visits already support legitimate commission and referral
    # reversals; keep that workflow and flag its receipts for finance review.
    if appt.status != Appointment.Status.COMPLETED:
        if invoice_line is not None:
            raise AppointmentLifecycleError(
                "برای این نوبت فاکتور صادر شده است؛ اصلاح سند باید از بخش مالی انجام شود."
            )
        if outstanding_receipts:
            raise AppointmentLifecycleError(
                "این نوبت پرداخت یا بیعانه دارد؛ ابتدا مبلغ را در بخش مالی مسترد کنید."
            )

    from apps.customers.models import Customer
    Customer.scoped(salon).select_for_update(no_key=True).get(pk=appt.customer_id)
    had_completed = appt.status == Appointment.Status.COMPLETED
    if had_completed:
        reverse_commission_for_appointment(appt)
        from apps.loyalty.automation import reverse_visit
        from apps.loyalty.benefits import reverse_referral
        reverse_referral(appt)
        reverse_visit(appt)

    appt.status = Appointment.Status.CANCELLED
    appt.cancelled_at = timezone.now()
    if had_completed:
        appt.completed_at = None
    appt.save(update_fields=["status", "cancelled_at", "completed_at", "updated_at"])
    from apps.retention.automation import queue_appointment_event
    queue_appointment_event(appt, "cancellation")
    refresh_customer_stats(appt.customer)
    if had_completed and (invoice_line is not None or outstanding_receipts):
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            salon=salon, action=AuditLog.Action.UPDATE,
            entity_type="appointment_finance_review", entity_id=str(appt.pk),
            message="لغو مراجعه تکمیل‌شده؛ بررسی و تطبیق اسناد مالی الزامی است",
            metadata={
                "appointment_id": appt.pk,
                "invoice_id": invoice_line.invoice_id if invoice_line else None,
                "unrefunded_receipts_toman": outstanding_receipts,
                "review_required": True,
            },
        )
    return appt