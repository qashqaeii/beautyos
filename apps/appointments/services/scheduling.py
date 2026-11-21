from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.staff.models import StaffProfile, StaffTimeOff, StaffWorkHours


class SchedulingError(ValidationError):
    pass


def _local_weekday(d: date) -> int:
    return (d.weekday() + 2) % 7


def staff_is_available(staff: StaffProfile, start: datetime, end: datetime) -> None:
    if not staff.is_active or not staff.is_bookable or staff.is_deleted:
        raise SchedulingError("متخصص در دسترس نیست.")

    local_start = timezone.localtime(start)
    local_end = timezone.localtime(end)
    if local_end <= local_start or local_end.date() != local_start.date():
        raise SchedulingError("بازه زمانی نامعتبر است.")

    if local_start < timezone.localtime():
        raise SchedulingError("رزرو در گذشته مجاز نیست.")

    weekday = _local_weekday(local_start.date())
    hours = StaffWorkHours.objects.filter(staff=staff, weekday=weekday).first()
    if hours is None or hours.is_closed:
        raise SchedulingError("در این روز سالن برای این متخصص تعطیل است.")
    if local_start.time() < hours.start_time or local_end.time() > hours.end_time:
        raise SchedulingError("خارج از ساعت کاری متخصص است.")

    if StaffTimeOff.objects.filter(
        staff=staff,
        start_date__lte=local_start.date(),
        end_date__gte=local_start.date(),
    ).exists():
        raise SchedulingError("متخصص در مرخصی است.")


def has_overlap(salon, staff_id, start: datetime, end: datetime, exclude_id=None) -> bool:
    qs = Appointment.scoped(salon).filter(
        staff_id=staff_id,
        status__in=[
            Appointment.Status.PENDING,
            Appointment.Status.CONFIRMED,
            Appointment.Status.CHECKED_IN,
        ],
        start_at__lt=end,
        end_at__gt=start,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


@transaction.atomic
def create_appointment(
    *,
    salon,
    customer,
    staff: StaffProfile,
    service,
    start: datetime,
    actor=None,
    source=Appointment.Source.INTERNAL,
    notes: str = "",
    status=None,
):
    if staff.salon_id != salon.pk or service.salon_id != salon.pk or customer.salon_id != salon.pk:
        raise SchedulingError("داده‌ها متعلق به این سالن نیستند.")

    staff = StaffProfile.scoped(salon).select_for_update().filter(pk=staff.pk).first()
    if staff is None or customer.is_deleted or not service.is_active or service.is_deleted:
        raise SchedulingError("اطلاعات رزرو دیگر معتبر نیست.")
    if not staff.services.filter(pk=service.pk).exists():
        raise SchedulingError("این متخصص این خدمت را ارائه نمی‌دهد.")
    if service.duration_minutes <= 0:
        raise SchedulingError("مدت خدمت معتبر نیست.")
    end = start + timedelta(minutes=service.duration_minutes)
    staff_is_available(staff, start, end)

    if has_overlap(salon, staff.pk, start, end):
        raise SchedulingError("این بازه با نوبت دیگری تداخل دارد.")

    appt = Appointment.objects.create(
        salon=salon,
        customer=customer,
        staff=staff,
        service=service,
        start_at=start,
        end_at=end,
        price_toman=service.price_toman,
        source=source,
        notes=notes,
        status=status or Appointment.Status.CONFIRMED,
    )

    if appt.status == Appointment.Status.CONFIRMED:
        from apps.retention.automation import queue_appointment_event
        queue_appointment_event(appt, "confirmation")

    from apps.customers.models import CustomerActivity
    from apps.customers.services import log_activity

    log_activity(
        salon=salon,
        customer=customer,
        activity_type=CustomerActivity.ActivityType.APPOINTMENT,
        title="رزرو نوبت",
        description=f"{service.name} — {timezone.localtime(start).strftime('%Y-%m-%d %H:%M')}",
        actor=actor,
        entity_type="appointment",
        entity_id=str(appt.pk),
    )
    return appt


def iter_day_slots(staff: StaffProfile, day: date, service_duration: int, step_minutes=15):
    if not staff.is_active or not staff.is_bookable or staff.is_deleted or service_duration <= 0 or step_minutes <= 0:
        return
    weekday = _local_weekday(day)
    hours = StaffWorkHours.objects.filter(staff=staff, weekday=weekday, is_closed=False).first()
    if not hours:
        return

    if StaffTimeOff.objects.filter(
        staff=staff, start_date__lte=day, end_date__gte=day
    ).exists():
        return

    tz = timezone.get_current_timezone()
    cursor = timezone.make_aware(datetime.combine(day, hours.start_time), tz)
    day_end = timezone.make_aware(datetime.combine(day, hours.end_time), tz)
    duration = timedelta(minutes=service_duration)

    while cursor + duration <= day_end:
        slot_end = cursor + duration
        if cursor >= timezone.now():
            if not has_overlap(staff.salon, staff.pk, cursor, slot_end):
                yield cursor
        cursor += timedelta(minutes=step_minutes)
