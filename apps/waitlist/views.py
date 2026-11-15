from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.appointments.services.confirmation import (
    AppointmentConfirmError,
    confirm_pending_appointment,
    pending_confirmation_queue,
)
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_APPOINTMENT_UPDATE, P_WAITLIST_MANAGE, require_permission


@salon_required
@require_permission(P_WAITLIST_MANAGE)
def queue(request):
    appointments = list(pending_confirmation_queue(request.salon))
    return render(
        request,
        "waitlist/queue.html",
        {
            "appointments": appointments,
            "queue_count": len(appointments),
        },
    )


@salon_required
@require_permission(P_WAITLIST_MANAGE)
@require_permission(P_APPOINTMENT_UPDATE)
@require_POST
def confirm_appointment(request, pk):
    try:
        _appt, confirmed = confirm_pending_appointment(salon=request.salon, appointment_id=pk)
    except AppointmentConfirmError as exc:
        messages.error(request, str(exc))
        return redirect("waitlist:queue")
    if confirmed:
        messages.success(request, "نوبت تأیید شد.")
    else:
        messages.info(request, "این نوبت قبلاً تأیید شده است.")
    return redirect("waitlist:queue")
