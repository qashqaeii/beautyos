from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.appointments.models import Appointment
from apps.appointments.services.confirmation import AppointmentConfirmError, confirm_pending_appointment
from apps.appointments.services.lifecycle import AppointmentLifecycleError, complete_appointment
from apps.audit.models import AuditLog
from apps.appointments.booking import appointment_booking_context
from apps.appointments.views import _appointment_qs
from apps.core.utils.dates import to_jalali
from apps.dashboard.role_services import get_reception_context, parse_dashboard_day
from apps.dashboard.nav import can_see_reception, reception_quick_access_links
from apps.reception.operations import day_operations
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role
from apps.salons.permissions_policy import (
    P_APPOINTMENT_CHECKIN,
    P_APPOINTMENT_COMPLETE,
    P_APPOINTMENT_CREATE,
    P_APPOINTMENT_UPDATE,
    P_PAYMENT_CREATE,
    P_STAFF_MANAGE,
    has_permission,
)


@salon_required
def desk(request):
    if not can_see_reception(request.membership):
        raise PermissionDenied
    membership = request.membership
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
    ctx = get_reception_context(
        request.salon,
        day,
        _appointment_qs(request).prefetch_related("payments"),
        service_id=service_pk,
        slot_staff_id=slot_staff_pk,
    )
    ctx.update(day_operations(salon=request.salon, queue=ctx["queue"]))
    ctx.update(
        {
            "day_jalali": to_jalali(day),
            "can_confirm": has_permission(membership, P_APPOINTMENT_UPDATE),
            "can_complete": has_permission(membership, P_APPOINTMENT_COMPLETE),
            "can_payment_create": has_permission(membership, P_PAYMENT_CREATE),
            "can_checkin": has_permission(membership, P_APPOINTMENT_CHECKIN),
            "can_manage_staff": has_permission(membership, P_STAFF_MANAGE),
            "prev_day": (day - timedelta(days=1)).isoformat(),
            "next_day": (day + timedelta(days=1)).isoformat(),
            "quick_access_links": reception_quick_access_links(membership),
            "can_book_appointment": has_permission(membership, P_APPOINTMENT_CREATE),
        }
    )
    booking_form = getattr(request, "booking_form_override", None)
    if request.GET.get("book") == "1" or booking_form is not None:
        ctx.update(
            appointment_booking_context(
                request,
                form=booking_form,
                book_modal_open=True,
            )
        )
    return render(request, "dashboard/reception_desk.html", ctx)


def _return_to_desk(request):
    """Use a validated date, never a user-supplied redirect destination."""
    raw = request.POST.get("day", "")
    try:
        day = date.fromisoformat(raw)
        if not 1900 <= day.year <= 2200:
            raise ValueError
    except (TypeError, ValueError):
        return redirect("reception:desk")
    return redirect(reverse("reception:desk") + "?" + urlencode({"day": day.isoformat()}))


def _audit_transition(request, appointment, title, previous):
    AuditLog.objects.create(
        salon=request.salon, actor=request.user, action=AuditLog.Action.UPDATE,
        entity_type="appointment", entity_id=str(appointment.pk), message=title,
        metadata={"from": previous, "to": appointment.status},
    )


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
@require_http_methods(["POST"])
def quick_confirm(request, pk):
    if not has_permission(request.membership, P_APPOINTMENT_UPDATE):
        raise PermissionDenied
    with transaction.atomic():
        appointment = get_object_or_404(
            Appointment.scoped(request.salon).select_for_update(), pk=pk,
        )
        previous = appointment.status
        try:
            appointment, changed = confirm_pending_appointment(
                salon=request.salon, appointment_id=pk,
            )
        except AppointmentConfirmError as exc:
            messages.error(request, str(exc))
        else:
            if changed:
                _audit_transition(request, appointment, "تأیید نوبت در پذیرش", previous)
                messages.success(request, "نوبت تأیید شد.")
            else:
                messages.info(request, "این نوبت قبلاً تأیید شده است.")
    return _return_to_desk(request)


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
@require_http_methods(["POST"])
def quick_checkin(request, pk):
    if not has_permission(request.membership, P_APPOINTMENT_CHECKIN):
        raise PermissionDenied
    with transaction.atomic():
        appt = get_object_or_404(
            Appointment.scoped(request.salon).select_for_update(), pk=pk,
        )
        if appt.status == Appointment.Status.CONFIRMED:
            previous = appt.status
            appt.status = Appointment.Status.CHECKED_IN
            appt.save(update_fields=["status", "updated_at"])
            _audit_transition(request, appt, "ثبت ورود مشتری در پذیرش", previous)
            messages.success(request, "ورود مشتری ثبت شد.")
        elif appt.status == Appointment.Status.CHECKED_IN:
            messages.info(request, "ورود این مشتری قبلاً ثبت شده است.")
        elif appt.status == Appointment.Status.PENDING:
            messages.error(request, "ابتدا این نوبت را تأیید کنید.")
        else:
            messages.error(request, "نوبت در وضعیت قابل پذیرش نیست.")
    return _return_to_desk(request)


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
@require_http_methods(["POST"])
def quick_complete(request, pk):
    if not has_permission(request.membership, P_APPOINTMENT_COMPLETE):
        raise PermissionDenied
    with transaction.atomic():
        appointment = get_object_or_404(
            Appointment.scoped(request.salon).select_for_update(), pk=pk,
        )
        previous = appointment.status
        if previous == Appointment.Status.COMPLETED:
            messages.info(request, "این مراجعه قبلاً تکمیل شده است.")
        elif previous not in (Appointment.Status.CONFIRMED, Appointment.Status.CHECKED_IN):
            messages.error(request, "فقط نوبت تأییدشده یا پذیرش‌شده قابل تکمیل است.")
        else:
            try:
                completed = complete_appointment(
                    salon=request.salon, appointment_id=appointment.pk,
                )
            except AppointmentLifecycleError as exc:
                messages.error(request, str(exc))
            else:
                _audit_transition(request, completed, "تکمیل مراجعه در پذیرش", previous)
                messages.success(request, "خدمت تکمیل شد؛ برای تسویه به صندوق مراجعه کنید.")
    return _return_to_desk(request)
