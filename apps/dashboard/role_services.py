"""Role-specific dashboard data — shared appointment source of truth."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.db.models import Count, Prefetch, Q, Sum
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.appointments.services.scheduling import iter_day_slots
from apps.commissions.models import CommissionEntry
from apps.customers.models import CustomerNote
from apps.dashboard.services import get_dashboard_kpis
from apps.finance.models import Payment
from apps.retention.models import FollowUp
from apps.services.models import Service
from apps.staff.models import StaffProfile, StaffTimeOff, StaffWorkHours


OCCUPYING_STATUSES = [
    Appointment.Status.PENDING,
    Appointment.Status.CONFIRMED,
    Appointment.Status.CHECKED_IN,
    Appointment.Status.COMPLETED,
]


def parse_dashboard_day(request) -> date:
    day_str = request.GET.get("day")
    if day_str:
        try:
            return datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    return timezone.localdate()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, datetime.min.time()), tz)
    end = start + timedelta(days=1)
    return start, end


def appointment_payment_summary(appt: Appointment) -> dict:
    payments = list(appt.payments.all())
    if not payments:
        owed = appt.price_toman
        return {
            "label": "بدون پرداخت",
            "owed_toman": owed,
            "paid_toman": 0,
            "status_code": "none",
        }
    latest = max(payments, key=lambda p: p.created_at)
    owed = sum(max(p.balance_toman, 0) for p in payments)
    paid = sum(p.paid_amount_toman for p in payments)
    return {
        "label": latest.get_status_display(),
        "owed_toman": owed,
        "paid_toman": paid,
        "status_code": latest.status,
    }


def _payments_in_range(salon, start: datetime, end: datetime):
    return Payment.scoped(salon).filter(created_at__gte=start, created_at__lt=end)


def get_manager_financial_summary(salon, pay_start: datetime, pay_end: datetime, appt_start: datetime, appt_end: datetime):
    pay_qs = _payments_in_range(salon, pay_start, pay_end).exclude(status=Payment.Status.REFUNDED)

    total_received = (
        pay_qs.filter(paid_amount_toman__gt=0).aggregate(t=Sum("paid_amount_toman"))["t"] or 0
    )

    deposit_qs = pay_qs.filter(status=Payment.Status.PARTIAL, paid_amount_toman__gt=0)
    deposits_amount = deposit_qs.aggregate(t=Sum("paid_amount_toman"))["t"] or 0
    deposits_appointments = deposit_qs.exclude(appointment_id=None).values("appointment_id").distinct().count()

    settled_qs = pay_qs.filter(status=Payment.Status.PAID)
    settled_count = settled_qs.count()
    settled_amount = settled_qs.aggregate(t=Sum("paid_amount_toman"))["t"] or 0

    appt_qs = (
        Appointment.scoped(salon)
        .filter(start_at__gte=appt_start, start_at__lt=appt_end)
        .exclude(status__in=[Appointment.Status.CANCELLED])
        .prefetch_related("payments")
    )
    receivable = 0
    receivable_appts = 0
    for appt in appt_qs:
        summary = appointment_payment_summary(appt)
        if summary["owed_toman"] > 0:
            receivable += summary["owed_toman"]
            receivable_appts += 1

    return {
        "total_received": total_received,
        "deposits_amount": deposits_amount,
        "deposits_appointment_count": deposits_appointments,
        "settled_count": settled_count,
        "settled_amount": settled_amount,
        "receivable_amount": receivable,
        "receivable_appointment_count": receivable_appts,
        "finance_range_label": "پرداخت‌های ثبت‌شده در بازهٔ انتخابی (بر اساس تاریخ ثبت پرداخت)",
        "receivable_range_label": "مانده بر اساس تاریخ نوبت در بازهٔ انتخابی",
    }


def staff_capacity_for_day(staff: StaffProfile, day: date, *, slot_duration: int = 30) -> dict | None:
    weekday = (day.weekday() + 2) % 7
    hours = StaffWorkHours.objects.filter(staff=staff, weekday=weekday, is_closed=False).first()
    if not hours:
        return None
    if StaffTimeOff.objects.filter(staff=staff, start_date__lte=day, end_date__gte=day).exists():
        return {
            "staff": staff,
            "booked_minutes": 0,
            "free_minutes": 0,
            "total_minutes": 0,
            "first_slot": None,
            "on_leave": True,
        }

    start_dt = datetime.combine(day, hours.start_time)
    end_dt = datetime.combine(day, hours.end_time)
    total_minutes = int((end_dt - start_dt).total_seconds() // 60)

    tz = timezone.get_current_timezone()
    bounds_start = timezone.make_aware(datetime.combine(day, datetime.min.time()), tz)
    bounds_end = bounds_start + timedelta(days=1)

    appts = Appointment.scoped(staff.salon).filter(
        staff=staff,
        start_at__gte=bounds_start,
        start_at__lt=bounds_end,
        status__in=OCCUPYING_STATUSES,
    )
    booked = 0
    for appt in appts:
        booked += int((appt.end_at - appt.start_at).total_seconds() // 60)

    free = max(0, total_minutes - booked)
    first_slot = next(iter_day_slots(staff, day, slot_duration), None)

    return {
        "staff": staff,
        "booked_minutes": booked,
        "free_minutes": free,
        "total_minutes": total_minutes,
        "first_slot": first_slot,
        "on_leave": False,
    }


def team_day_calendar(salon, day: date, appointment_qs):
    start, end = day_bounds(day)
    staff_list = (
        StaffProfile.scoped(salon)
        .filter(is_active=True, is_deleted=False, is_bookable=True)
        .prefetch_related("services")
        .order_by("display_name")
    )
    appts = list(
        appointment_qs.filter(start_at__gte=start, start_at__lt=end).order_by("start_at")
    )
    by_staff: dict[int, list] = {s.pk: [] for s in staff_list}
    for appt in appts:
        if appt.staff_id and appt.staff_id in by_staff:
            by_staff[appt.staff_id].append(appt)

    columns = []
    for staff in staff_list:
        capacity = staff_capacity_for_day(staff, day)
        columns.append(
            {
                "staff": staff,
                "appointments": by_staff.get(staff.pk, []),
                "capacity": capacity,
            }
        )
    return columns


def reception_staff_day_status(capacity: dict | None) -> str:
    if not capacity:
        return "ساعت کاری ثبت نشده"
    if capacity.get("on_leave"):
        return "مرخصی امروز"
    if capacity.get("total_minutes", 0) <= 0:
        return "ساعت کاری ثبت نشده"
    if capacity.get("free_minutes", 0) <= 0:
        return "وقت آزاد ندارد"
    return f"{capacity['free_minutes']} دقیقه آزاد"


def bookable_staff_for_service(salon, service: Service):
    return (
        StaffProfile.scoped(salon)
        .filter(is_active=True, is_deleted=False, is_bookable=True, services=service)
        .distinct()
        .order_by("display_name", "pk")
    )


def first_available_slots(
    salon,
    day: date,
    service: Service,
    *,
    staff_id: int | None = None,
) -> list[dict]:
    staff_qs = bookable_staff_for_service(salon, service)
    if staff_id is not None:
        staff_qs = staff_qs.filter(pk=staff_id)
    rows = []
    duration = service.duration_minutes
    for staff in staff_qs:
        slot = next(iter_day_slots(staff, day, duration), None)
        if slot:
            rows.append({"staff": staff, "start": slot, "service": service})
    rows.sort(key=lambda r: r["start"])
    return rows


def get_manager_followups(salon):
    today = timezone.localdate()
    pending_appts = (
        Appointment.scoped(salon)
        .filter(status=Appointment.Status.PENDING, start_at__gte=timezone.now())
        .select_related("customer", "service", "staff")
        .order_by("start_at")[:15]
    )
    unpaid_deposits = (
        Payment.scoped(salon)
        .filter(status=Payment.Status.PARTIAL)
        .select_related("customer", "appointment", "appointment__service")
        .order_by("-created_at")[:15]
    )
    due_followups = (
        FollowUp.scoped(salon)
        .filter(status=FollowUp.Status.OPEN)
        .filter(Q(next_follow_up_at__lte=today) | Q(next_follow_up_at__isnull=True))
        .select_related("customer")[:15]
    )
    return {
        "pending_appointments": pending_appts,
        "unpaid_deposits": unpaid_deposits,
        "due_followups": due_followups,
    }


def get_overview_context(salon, membership, day: date, pay_start: datetime, pay_end: datetime):
    from apps.salons.permissions_policy import P_FINANCE_REPORTS, has_permission

    start, end = day_bounds(day)
    appt_qs = Appointment.scoped(salon).filter(start_at__gte=start, start_at__lt=end)
    overview = {
        "appointments_count": appt_qs.exclude(status=Appointment.Status.CANCELLED).count(),
        "pending_count": appt_qs.filter(status=Appointment.Status.PENDING).count(),
    }
    finance = None
    if has_permission(membership, P_FINANCE_REPORTS):
        finance = get_manager_financial_summary(salon, pay_start, pay_end, start, end)
    return {
        "overview": overview,
        "finance": finance,
        "selected_day": day,
    }


def get_manager_context(salon, day: date, pay_start: datetime, pay_end: datetime):
    appt_start, appt_end = day_bounds(day)
    kpis = get_dashboard_kpis(salon)
    finance = get_manager_financial_summary(salon, pay_start, pay_end, appt_start, appt_end)
    followups = get_manager_followups(salon)
    staff_capacity = []
    for staff in StaffProfile.scoped(salon).filter(is_active=True, is_deleted=False, is_bookable=True):
        cap = staff_capacity_for_day(staff, day)
        if cap:
            staff_capacity.append(cap)

    return {
        "kpis": kpis,
        "finance": finance,
        "followups": followups,
        "staff_capacity": staff_capacity,
        "selected_day": day,
        "calendar_columns": team_day_calendar(salon, day, Appointment.scoped(salon).select_related("customer", "service", "staff")),
    }


def get_reception_context(
    salon,
    day: date,
    appointment_qs,
    *,
    service_id: int | None = None,
    staff_filter_id: int | None = None,
    slot_staff_id: int | None = None,
):
    start, end = day_bounds(day)
    queue = appointment_qs.filter(start_at__gte=start, start_at__lt=end).order_by("start_at")
    now = timezone.now()
    next_appt = (
        appointment_qs.filter(
            start_at__gte=now,
            status__in=[
                Appointment.Status.PENDING,
                Appointment.Status.CONFIRMED,
                Appointment.Status.CHECKED_IN,
            ],
        )
        .select_related("customer", "service", "staff")
        .prefetch_related("payments")
        .order_by("start_at")
        .first()
    )
    pending_confirm = (
        Appointment.scoped(salon)
        .filter(status=Appointment.Status.PENDING)
        .select_related("customer", "service", "staff")
        .order_by("start_at")[:20]
    )
    services = Service.scoped(salon).filter(is_active=True, is_deleted=False).order_by("name")
    selected_service = None
    first_slots = []
    bookable_staff_for_service_list: list = []
    selected_slot_staff_id = None
    slot_staff_no_availability = False
    if service_id:
        selected_service = services.filter(pk=service_id).first()
        if selected_service:
            bookable_staff_for_service_list = list(bookable_staff_for_service(salon, selected_service))
            valid_staff_ids = {s.pk for s in bookable_staff_for_service_list}
            if slot_staff_id is not None and slot_staff_id in valid_staff_ids:
                selected_slot_staff_id = slot_staff_id
            if selected_slot_staff_id:
                first_slots = first_available_slots(
                    salon, day, selected_service, staff_id=selected_slot_staff_id
                )
                slot_staff_no_availability = len(first_slots) == 0
            else:
                first_slots = first_available_slots(salon, day, selected_service)

    team_qs = appointment_qs
    if staff_filter_id:
        team_qs = team_qs.filter(staff_id=staff_filter_id)
    calendar_columns = team_day_calendar(salon, day, team_qs)
    staff_roster = []
    for col in calendar_columns:
        staff = col["staff"]
        cap = col["capacity"] or {}
        staff_roster.append(
            {
                "staff": staff,
                "services": staff.services.filter(is_active=True, is_deleted=False),
                "capacity": cap,
                "day_status": reception_staff_day_status(cap),
            }
        )

    next_payment = appointment_payment_summary(next_appt) if next_appt else None

    return {
        "selected_day": day,
        "queue": queue,
        "next_appt": next_appt,
        "next_payment": next_payment,
        "pending_confirm": pending_confirm,
        "services": services,
        "selected_service": selected_service,
        "first_slots": first_slots,
        "bookable_staff_for_service": bookable_staff_for_service_list,
        "selected_slot_staff_id": selected_slot_staff_id,
        "slot_staff_no_availability": slot_staff_no_availability,
        "calendar_columns": calendar_columns,
        "staff_roster": staff_roster,
        "staff_filter_id": staff_filter_id,
        "summary": {
            "today_total": queue.count(),
            "pending": queue.filter(
                status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED]
            ).count(),
            "checked_in": queue.filter(status=Appointment.Status.CHECKED_IN).count(),
        },
    }


def get_specialist_context(salon, membership, day: date):
    profile = getattr(membership, "staff_profile", None)
    if profile is None:
        profile = StaffProfile.objects.filter(membership=membership).first()

    start, end = day_bounds(day)
    appointments = []
    if profile:
        appointments = list(
            Appointment.scoped(salon)
            .filter(staff=profile, start_at__gte=start, start_at__lt=end)
            .select_related("customer", "service")
            .prefetch_related(
                Prefetch("customer__notes", queryset=CustomerNote.objects.order_by("-created_at")[:3])
            )
            .order_by("start_at")
        )

    now = timezone.now()
    next_appt = next(
        (
            a
            for a in appointments
            if a.start_at >= now
            and a.status
            not in (Appointment.Status.COMPLETED, Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW)
        ),
        None,
    )

    commission_summary = None
    from apps.salons.models import SalonSettings
    from apps.salons.permissions_policy import P_COMMISSION_VIEW_SELF, has_permission

    settings = SalonSettings.objects.filter(salon=salon).first()
    if profile and has_permission(membership, P_COMMISSION_VIEW_SELF) and (
        settings is None or settings.specialist_can_view_commission
    ):
        month_start = timezone.localdate().replace(day=1)
        entries = CommissionEntry.scoped(salon).filter(staff=profile, created_at__date__gte=month_start)
        commission_summary = {
            "recognized": entries.filter(status=CommissionEntry.Status.RECOGNIZED).aggregate(
                t=Sum("commission_amount_toman")
            )["t"]
            or 0,
            "settled": entries.filter(status=CommissionEntry.Status.SETTLED).aggregate(
                t=Sum("commission_amount_toman")
            )["t"]
            or 0,
        }

    return {
        "profile": profile,
        "selected_day": day,
        "appointments": appointments,
        "next_appt": next_appt,
        "commission_summary": commission_summary,
    }
