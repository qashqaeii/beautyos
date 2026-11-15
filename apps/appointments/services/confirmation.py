from __future__ import annotations

from django.db import transaction

from apps.appointments.models import Appointment


class AppointmentConfirmError(Exception):
    """User-facing confirmation failure."""


@transaction.atomic
def confirm_pending_appointment(*, salon, appointment_id: int) -> tuple[Appointment, bool]:
    """
    Confirm a pending appointment. Returns (appointment, created_confirmation).
    `created_confirmation` is False when already confirmed (idempotent).
    """
    try:
        appt = (
            Appointment.scoped(salon)
            .select_for_update()
            .select_related("customer", "service", "staff")
            .get(pk=appointment_id)
        )
    except Appointment.DoesNotExist as exc:
        raise AppointmentConfirmError("نوبت یافت نشد یا متعلق به این سالن نیست.") from exc

    if appt.status == Appointment.Status.CONFIRMED:
        return appt, False
    if appt.status != Appointment.Status.PENDING:
        raise AppointmentConfirmError("این نوبت دیگر در انتظار تأیید نیست.")

    appt.status = Appointment.Status.CONFIRMED
    appt.save(update_fields=["status", "updated_at"])
    return appt, True


def pending_confirmation_queue(salon):
    return (
        Appointment.scoped(salon)
        .filter(status=Appointment.Status.PENDING)
        .select_related("customer", "service", "staff")
        .order_by("created_at")
    )
