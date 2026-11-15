from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.appointments.booking import (
    appointment_booking_context,
    appointment_booking_form,
    render_booking_host,
    safe_booking_return_path,
)
from apps.appointments.forms import AppointmentForm
from apps.appointments.models import Appointment
from apps.appointments.services.lifecycle import AppointmentLifecycleError, cancel_appointment, complete_appointment
from apps.appointments.services.scheduling import SchedulingError, create_appointment
from apps.core.utils.dates import (
    JALALI_MONTH_NAMES_FA,
    add_jalali_months,
    date_in_jalali_month,
    gregorian_bounds_for_jalali_month,
    jalali_month_query_value,
    parse_jalali_month_param,
    to_jalali,
)
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.staff.calendar_colors import resolve_staff_calendar_color, staff_color_map
from apps.staff.models import StaffProfile
from apps.salons.permissions import require_role
from apps.finance.services import create_appointment_deposit
from apps.salons.permissions_policy import (
    P_APPOINTMENT_CREATE,
    P_APPOINTMENT_VIEW,
    has_permission,
    require_permission,
)


def _appointment_qs(request):
    qs = Appointment.scoped(request.salon).select_related("customer", "staff", "service")
    if request.membership.role == SalonMembership.Role.SPECIALIST:
        profile = getattr(request.membership, "staff_profile", None)
        if profile:
            qs = qs.filter(staff=profile)
    staff_id = request.GET.get("staff")
    status = request.GET.get("status")
    if staff_id:
        try:
            sid = int(staff_id)
            if StaffProfile.scoped(request.salon).filter(pk=sid, is_deleted=False).exists():
                qs = qs.filter(staff_id=sid)
        except (TypeError, ValueError):
            pass
    if status:
        qs = qs.filter(status=status)
    return qs


@salon_required
@require_permission(P_APPOINTMENT_VIEW)
def calendar_day(request):
    from apps.appointments.services.calendar_month import (
        build_jalali_month_grid,
        staff_dots_by_day,
    )
    today = timezone.localdate()
    membership = request.membership

    selected_day: date | None = None
    day_str = request.GET.get("day")
    if day_str:
        try:
            selected_day = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            selected_day = None

    month_fallback = selected_day or today
    jy, jm = parse_jalali_month_param(request.GET.get("month"), month_fallback)
    if selected_day and not date_in_jalali_month(selected_day, jy, jm):
        selected_day = None

    if selected_day is None and date_in_jalali_month(today, jy, jm):
        selected_day = today

    month_start, month_end = gregorian_bounds_for_jalali_month(jy, jm)
    range_start = timezone.make_aware(datetime.combine(month_start, datetime.min.time()))
    range_end = timezone.make_aware(datetime.combine(month_end + timedelta(days=1), datetime.min.time()))

    month_qs = _appointment_qs(request).filter(
        start_at__gte=range_start,
        start_at__lt=range_end,
    )
    if membership.role == SalonMembership.Role.SPECIALIST:
        profile = getattr(membership, "staff_profile", None)
        if profile:
            month_qs = month_qs.filter(staff=profile)
        else:
            month_qs = month_qs.none()

    month_appointments = list(month_qs.select_related("customer", "staff", "service").order_by("start_at"))
    dots = staff_dots_by_day(month_appointments)

    day_appointments = []
    if selected_day:
        day_appointments = [
            a
            for a in month_appointments
            if timezone.localtime(a.start_at).date() == selected_day
        ]

    prev_jy, prev_jm = add_jalali_months(jy, jm, -1)
    next_jy, next_jm = add_jalali_months(jy, jm, 1)
    month_param = jalali_month_query_value(jy, jm)
    prev_month_param = jalali_month_query_value(prev_jy, prev_jm)
    next_month_param = jalali_month_query_value(next_jy, next_jm)

    def day_param_for_month(target_jy: int, target_jm: int) -> str:
        if selected_day and date_in_jalali_month(selected_day, target_jy, target_jm):
            return f"&day={selected_day.isoformat()}"
        return ""

    filter_staff_id = None
    staff_param = request.GET.get("staff")
    if staff_param:
        try:
            sid = int(staff_param)
            if StaffProfile.scoped(request.salon).filter(pk=sid, is_deleted=False).exists():
                filter_staff_id = sid
        except (TypeError, ValueError):
            filter_staff_id = None

    staff_suffix = f"&staff={filter_staff_id}" if filter_staff_id else ""

    calendar_staff_qs = StaffProfile.scoped(request.salon).filter(
        is_deleted=False,
        is_active=True,
        is_bookable=True,
    )
    if membership.role == SalonMembership.Role.SPECIALIST:
        profile = getattr(membership, "staff_profile", None)
        if profile:
            calendar_staff_qs = calendar_staff_qs.filter(pk=profile.pk)
        else:
            calendar_staff_qs = calendar_staff_qs.none()

    calendar_staff = list(calendar_staff_qs.select_related("membership__user").order_by("display_name"))
    colors_by_staff = staff_color_map(calendar_staff)

    selected_staff = None
    if filter_staff_id:
        selected_staff = next((s for s in calendar_staff if s.pk == filter_staff_id), None)
    selected_staff_color = resolve_staff_calendar_color(selected_staff) if selected_staff else None

    show_staff_filter = membership.role != SalonMembership.Role.SPECIALIST and len(calendar_staff) > 0
    staff_filter_label = selected_staff.full_display_name if selected_staff else "همه متخصصان"

    _STAFF_Q_UNSET = object()

    def calendar_query(
        *,
        month: str | None = None,
        day: date | None = None,
        staff_id: int | None | object = _STAFF_Q_UNSET,
    ) -> str:
        parts = [f"month={month or month_param}"]
        d = day if day is not None else selected_day
        if d:
            parts.append(f"day={d.isoformat()}")
        if staff_id is _STAFF_Q_UNSET:
            sid = filter_staff_id
        else:
            sid = staff_id
        if sid:
            parts.append(f"staff={sid}")
        return "&".join(parts)

    can_book = has_permission(membership, P_APPOINTMENT_CREATE)
    calendar_month = build_jalali_month_grid(
        jy,
        jm,
        today=today,
        selected_day=selected_day,
        dots_by_day=dots,
        staff_colors=colors_by_staff,
        selected_staff_color=selected_staff_color,
    )

    ctx = {
        "can_book_appointment": can_book,
        "jalali_year": jy,
        "jalali_month": jm,
        "jalali_month_name": JALALI_MONTH_NAMES_FA[jm - 1],
        "month_param": month_param,
        "prev_month_href": f"?{calendar_query(month=prev_month_param, day=selected_day if selected_day and date_in_jalali_month(selected_day, prev_jy, prev_jm) else None)}",
        "next_month_href": f"?{calendar_query(month=next_month_param, day=selected_day if selected_day and date_in_jalali_month(selected_day, next_jy, next_jm) else None)}",
        "calendar_month": calendar_month,
        "selected_day": selected_day,
        "day_jalali": to_jalali(selected_day) if selected_day else "",
        "appointments": day_appointments,
        "staff_suffix": staff_suffix,
        "month_query": calendar_query(),
        "calendar_staff": calendar_staff,
        "calendar_staff_colors": colors_by_staff,
        "selected_staff": selected_staff,
        "selected_staff_id": filter_staff_id,
        "show_staff_filter": show_staff_filter,
        "staff_filter_label": staff_filter_label,
        "show_staff_legend": show_staff_filter and not filter_staff_id and len(calendar_staff) > 1,
        "staff_filter_all_query": calendar_query(staff_id=None),
        "staff_filter_queries": {s.pk: calendar_query(staff_id=s.pk) for s in calendar_staff},
    }
    booking_form = getattr(request, "booking_form_override", None)
    if request.GET.get("book") == "1" or booking_form is not None:
        ctx.update(
            appointment_booking_context(
                request,
                form=booking_form,
                book_modal_open=True,
            )
        )
    return render(request, "appointments/calendar_day.html", ctx)


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def calendar_week(request):
    week_start_str = request.GET.get("week")
    if week_start_str:
        try:
            week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        except ValueError:
            week_start = timezone.localdate()
    else:
        today = timezone.localdate()
        week_start = today - timedelta(days=(today.weekday() + 2) % 7)

    days = [week_start + timedelta(days=i) for i in range(7)]
    range_start = timezone.make_aware(datetime.combine(days[0], datetime.min.time()))
    range_end = range_start + timedelta(days=7)
    appointments = list(
        _appointment_qs(request)
        .filter(start_at__gte=range_start, start_at__lt=range_end)
        .order_by("start_at")
    )
    by_day = {d: [] for d in days}
    for appt in appointments:
        local_day = timezone.localtime(appt.start_at).date()
        if local_day in by_day:
            by_day[local_day].append(appt)

    from apps.staff.models import StaffProfile

    staff_list = StaffProfile.scoped(request.salon).filter(is_active=True, is_deleted=False)
    today = timezone.localdate()
    hours = list(range(8, 22))
    return render(
        request,
        "appointments/calendar_week.html",
        {
            "week_start": week_start,
            "week_end": days[-1],
            "days": days,
            "by_day": by_day,
            "staff_list": staff_list,
            "hours": hours,
            "today": today,
            "prev_week": (week_start - timedelta(days=7)).isoformat(),
            "next_week": (week_start + timedelta(days=7)).isoformat(),
        },
    )


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def appointment_list(request):
    qs = _appointment_qs(request).order_by("-start_at")[:100]
    return render(request, "appointments/list.html", {"appointments": qs})


def _render_customer_detail_booking_error(request, customer_id: int, form):
    from apps.customers.views import _customer_detail_context, _get_customer

    customer = _get_customer(request, customer_id)
    ctx = _customer_detail_context(
        request,
        customer,
        appointment_form=form,
        book_modal_open=True,
    )
    return render(request, "customers/detail.html", ctx)


@salon_required
@require_permission(P_APPOINTMENT_CREATE)
def appointment_create(request):
    membership = request.membership
    if request.method == "GET":
        customer_id = request.GET.get("customer")
        if customer_id and request.GET.get("book") != "1":
            try:
                cid = int(customer_id)
                params = request.GET.copy()
                params.pop("customer", None)
                params["book"] = "1"
                qs = params.urlencode()
                return redirect(f"{reverse('customers:detail', kwargs={'pk': cid})}?{qs}" if qs else f"{reverse('customers:detail', kwargs={'pk': cid})}?book=1")
            except (TypeError, ValueError):
                pass

    if request.method == "POST":
        form = appointment_booking_form(request, data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                with transaction.atomic():
                    customer = form.resolve_customer(actor=request.user)
                    appt = create_appointment(
                        salon=request.salon,
                        customer=customer,
                        staff=data["staff"],
                        service=data["service"],
                        start=data["start_at"],
                        actor=request.user,
                        notes=data.get("notes", ""),
                        status=data.get("status") or Appointment.Status.CONFIRMED,
                    )
                    deposit = data.get("deposit_amount_toman") or 0
                    if deposit > 0:
                        create_appointment_deposit(
                            salon=request.salon,
                            customer=customer,
                            appointment=appt,
                            amount_toman=deposit,
                            method=data["deposit_method"],
                        )
                messages.success(request, f"نوبت ثبت شد. کد: {appt.tracking_code}")
                return_path = safe_booking_return_path(request.POST.get("booking_return_path"))
                if return_path:
                    return redirect(return_path)
                return redirect("appointments:detail", pk=appt.pk)
            except ValidationError as exc:
                msg = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
                form.add_error(None, msg)
        return_path = safe_booking_return_path(request.POST.get("booking_return_path"))
        if return_path and return_path != reverse("appointments:create"):
            return render_booking_host(request, return_path, form)
        from_customer = request.POST.get("from_customer_detail")
        if from_customer:
            try:
                return _render_customer_detail_booking_error(request, int(from_customer), form)
            except (TypeError, ValueError, Http404):
                pass
        ctx = appointment_booking_context(request, form=form, book_modal_open=True)
        return render(request, "appointments/form.html", ctx)
    else:
        form = appointment_booking_form(request)
    ctx = appointment_booking_context(request, form=form, book_modal_open=True)
    return render(request, "appointments/form.html", ctx)


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def appointment_detail(request, pk):
    appt = get_object_or_404(_appointment_qs(request), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "cancel":
                cancel_appointment(salon=request.salon, appointment_id=appt.pk)
                messages.success(request, "نوبت لغو شد.")
            elif action == "complete":
                complete_appointment(salon=request.salon, appointment_id=appt.pk)
                messages.success(request, "مراجعه تکمیل شد.")
        except AppointmentLifecycleError as exc:
            messages.error(request, str(exc))
        return redirect("appointments:detail", pk=pk)
    return render(request, "appointments/detail.html", {"appointment": appt})
