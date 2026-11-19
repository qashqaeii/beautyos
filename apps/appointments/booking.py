from __future__ import annotations

from datetime import datetime, time, timedelta
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render
from django.urls import resolve, reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.appointments.forms import AppointmentForm
from apps.appointments.models import Appointment
from apps.appointments.picker_context import resolve_customer_picker_context
from apps.customers.models import Customer
from apps.dashboard.role_services import get_reception_context, parse_dashboard_day
from apps.dashboard.nav import can_see_reception, reception_quick_access_links
from apps.salons.permissions_policy import (
    P_APPOINTMENT_CHECKIN,
    P_APPOINTMENT_CREATE,
    P_PAYMENT_CREATE,
    P_STAFF_MANAGE,
    has_permission,
)
from apps.services.models import Service
from apps.staff.models import StaffProfile


def resolve_booking_locked_staff(request, salon) -> StaffProfile | None:
    """Staff preset from «رزرو برای این متخصص» (?staff=) or hidden field on POST."""
    raw = None
    if request.method == "POST":
        raw = (request.POST.get("booking_staff_locked") or "").strip()
    if not raw:
        raw = (request.GET.get("staff") or "").strip()
    if not raw:
        return None
    try:
        pk = int(raw)
    except (TypeError, ValueError):
        return None
    if not 0 < pk <= 2**63 - 1:
        return None
    return (
        StaffProfile.scoped(salon)
        .filter(pk=pk, is_active=True, is_deleted=False, is_bookable=True)
        .first()
    )


def safe_booking_return_path(path: str | None) -> str | None:
    if not path or not isinstance(path, str):
        return None
    path = path.strip()
    if not path.startswith("/") or path.startswith("//") or "\\" in path or "://" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        return None
    if not url_has_allowed_host_and_scheme(path, allowed_hosts=set()):
        return None
    if len(path) > 512:
        return None
    return path


def parse_appointment_initial_from_request(request) -> dict:
    initial: dict = {}
    try:
        staff_id = request.GET.get("staff")
        service_id = request.GET.get("service")
        customer_id = request.GET.get("customer")
        if staff_id:
            initial["staff"] = int(staff_id)
        if service_id:
            initial["service"] = int(service_id)
        if customer_id:
            customer = Customer.scoped(request.salon).filter(pk=int(customer_id), is_deleted=False).first()
            if customer:
                initial["customer"] = customer
        start_raw = (request.GET.get("start") or "").replace(" ", "+")
        if start_raw:
            from django.utils.dateparse import parse_datetime

            start_dt = parse_datetime(start_raw)
            if start_dt:
                if timezone.is_naive(start_dt):
                    start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
                local_start = timezone.localtime(start_dt)
                initial["appointment_date"] = local_start.date()
                initial["appointment_time"] = local_start.time().replace(second=0, microsecond=0)
        day_str = request.GET.get("day")
        if day_str and "appointment_date" not in initial:
            try:
                day = datetime.strptime(day_str, "%Y-%m-%d").date()
                initial["appointment_date"] = day
                if "appointment_time" not in initial:
                    initial["appointment_time"] = time(9, 0)
            except ValueError:
                pass
    except (TypeError, ValueError):
        initial = {}
    return initial


def booking_advanced_open(form: AppointmentForm) -> bool:
    if not form or form.is_bound is False:
        return False
    touch_fields = ("deposit_amount_toman", "deposit_method", "notes", "status")
    for name in touch_fields:
        if name in form.errors:
            return True
        if name not in form.fields:
            continue
        raw = form.data.get(name, "")
        if isinstance(raw, str) and raw.strip():
            return True
        if name == "status" and raw and raw != Appointment.Status.CONFIRMED:
            return True
    return False


def appointment_booking_form(
    request,
    *,
    data=None,
    initial: dict | None = None,
    locked_staff: StaffProfile | None = None,
) -> AppointmentForm:
    membership = request.membership
    locked_staff = locked_staff or resolve_booking_locked_staff(request, request.salon)
    if data is not None:
        form = AppointmentForm(
            data,
            salon=request.salon,
            membership=membership,
            locked_staff=locked_staff,
        )
        if data.get("booking_staff_locked") and locked_staff is None:
            form.add_error(None, "متخصص انتخاب‌شده دیگر قابل رزرو نیست. متخصص دیگری را انتخاب کنید.")
        return form
    if initial is None:
        initial = parse_appointment_initial_from_request(request)
    if locked_staff:
        initial["staff"] = locked_staff.pk
    return AppointmentForm(
        salon=request.salon,
        membership=membership,
        initial=initial,
        locked_staff=locked_staff,
    )


def appointment_booking_context(
    request,
    *,
    form: AppointmentForm | None = None,
    book_modal_open: bool = False,
    customer_locked=None,
) -> dict:
    membership = request.membership
    if form is None:
        form = appointment_booking_form(request)
    can_payment_create = has_permission(membership, P_PAYMENT_CREATE)
    service_prices = {}
    if can_payment_create:
        service_prices = {
            str(s.pk): s.price_toman
            for s in Service.scoped(request.salon).filter(is_active=True, is_deleted=False)
        }
    picker_ctx = resolve_customer_picker_context(form=form, membership=membership, salon=request.salon)
    picker_ctx["customer_picker_config"]["searchUrl"] = reverse("customers:search")
    params = request.GET.copy()
    params.pop("book", None)
    qs = params.urlencode()
    booking_return_path = request.path + (f"?{qs}" if qs else "")
    if form.is_bound:
        booking_return_path = safe_booking_return_path(form.data.get("booking_return_path")) or booking_return_path

    locked_staff = getattr(form, "locked_staff", None) or resolve_booking_locked_staff(request, request.salon)

    return {
        "appointment_form": form,
        "form": form,
        "book_modal_open": book_modal_open,
        "booking_staff_locked": locked_staff,
        "booking_staff_has_no_services": bool(locked_staff and not form.fields["service"].queryset.exists()),
        "booking_advanced_open": booking_advanced_open(form),
        "booking_return_path": booking_return_path,
        "customer_search_url": reverse("customers:search"),
        "can_payment_create": can_payment_create,
        "service_prices": service_prices,
        "customer_locked": customer_locked,
        "can_book_appointment": has_permission(membership, P_APPOINTMENT_CREATE),
        **picker_ctx,
    }


def _query_dict_from_return_path(return_path: str) -> dict:
    parsed = urlparse(return_path)
    q = parse_qs(parsed.query, keep_blank_values=True)
    flat = {k: (v[0] if v else "") for k, v in q.items()}
    flat.pop("book", None)
    return flat


def _fake_get_for_return(request, return_path: str):
    """Merge return-path query params into a copy of GET for context builders."""
    from django.http import QueryDict

    q = _query_dict_from_return_path(return_path)
    merged = request.GET.copy()
    for key, val in q.items():
        merged[key] = val
    request.GET = merged
    return request


def render_booking_host(request, return_path: str, form: AppointmentForm):
    return_path = safe_booking_return_path(return_path) or reverse("appointments:create")
    parsed = urlparse(return_path)
    try:
        match = resolve(parsed.path)
    except Http404:
        ctx = appointment_booking_context(request, form=form, book_modal_open=True)
        return render(request, "appointments/form.html", ctx)

    url_name = match.url_name
    namespace = match.namespace

    if namespace == "reception" and url_name == "desk":
        from apps.appointments.views import _appointment_qs

        request.booking_form_override = form
        if not can_see_reception(request.membership):
            raise Http404
        _fake_get_for_return(request, return_path)
        day = parse_dashboard_day(request)
        service_id = request.GET.get("service")
        staff_id = request.GET.get("staff")
        try:
            service_pk = int(service_id) if service_id else None
        except (TypeError, ValueError):
            service_pk = None
        try:
            slot_staff_pk = int(staff_id) if staff_id else None
        except (TypeError, ValueError):
            slot_staff_pk = None
        membership = request.membership
        ctx = get_reception_context(
            request.salon,
            day,
            _appointment_qs(request).prefetch_related("payments"),
            service_id=service_pk,
            slot_staff_id=slot_staff_pk,
        )
        from apps.core.utils.dates import to_jalali

        ctx.update(
            {
                "day_jalali": to_jalali(day),
                "can_checkin": has_permission(membership, P_APPOINTMENT_CHECKIN),
                "can_manage_staff": has_permission(membership, P_STAFF_MANAGE),
                "prev_day": (day - timedelta(days=1)).isoformat(),
                "next_day": (day + timedelta(days=1)).isoformat(),
                "quick_access_links": reception_quick_access_links(membership),
            }
        )
        ctx.update(appointment_booking_context(request, form=form, book_modal_open=True))
        return render(request, "dashboard/reception_desk.html", ctx)

    if namespace == "appointments" and url_name == "calendar":
        from apps.appointments import views as appt_views

        request.booking_form_override = form
        _fake_get_for_return(request, return_path)
        return appt_views.calendar_day(request)

    if namespace == "dashboard" and url_name == "specialists":
        from apps.dashboard import views as dashboard_views

        request.booking_form_override = form
        _fake_get_for_return(request, return_path)
        return dashboard_views.specialists(request)

    if namespace == "staff" and url_name == "detail":
        from apps.staff import views as staff_views
        from apps.staff.models import StaffProfile

        pk = match.kwargs.get("pk")
        profile = StaffProfile.scoped(request.salon).filter(pk=pk, is_deleted=False).first()
        if not profile:
            raise Http404
        if not has_permission(request.membership, P_STAFF_MANAGE):
            raise PermissionDenied
        if getattr(form, "locked_staff", None) is None or form.locked_staff.pk != profile.pk:
            ctx = appointment_booking_context(request, form=form, book_modal_open=True)
            return render(request, "appointments/form.html", ctx)
        ctx = staff_views._staff_detail_context(
            request, profile, booking_form=form, book_modal_open=True,
        )
        return render(request, "staff/detail.html", ctx)

    if namespace == "customers" and url_name == "detail":
        from apps.customers import views as customer_views

        pk = match.kwargs["pk"]
        customer = customer_views._get_customer(request, pk)
        ctx = customer_views._customer_detail_context(
            request,
            customer,
            appointment_form=form,
            book_modal_open=True,
        )
        return render(request, "customers/detail.html", ctx)

    ctx = appointment_booking_context(request, form=form, book_modal_open=True)
    return render(request, "appointments/form.html", ctx)