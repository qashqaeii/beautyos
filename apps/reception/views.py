from datetime import timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.appointments.models import Appointment
from apps.appointments.booking import appointment_booking_context
from apps.appointments.views import _appointment_qs
from apps.core.utils.dates import to_jalali
from apps.dashboard.role_services import get_reception_context, parse_dashboard_day
from apps.dashboard.nav import can_see_reception, reception_quick_access_links
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role
from apps.salons.permissions_policy import (
    P_APPOINTMENT_CHECKIN,
    P_APPOINTMENT_CREATE,
    P_STAFF_MANAGE,
    has_permission,
)


@salon_required
def desk(request):
    if not can_see_reception(request.membership):
        from django.core.exceptions import PermissionDenied

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
    ctx.update(
        {
            "day_jalali": to_jalali(day),
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


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def quick_checkin(request, pk):
    from django.urls import reverse

    appt = get_object_or_404(_appointment_qs(request), pk=pk)
    if appt.status in (Appointment.Status.CONFIRMED, Appointment.Status.PENDING):
        appt.status = Appointment.Status.CHECKED_IN
        appt.save(update_fields=["status", "updated_at"])
        messages.success(request, "پذیرش انجام شد.")
    return redirect("reception:desk")
