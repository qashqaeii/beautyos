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
    Appointment.Status.PENDING,
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
    refresh_customer_stats(appt.customer)
    return appt