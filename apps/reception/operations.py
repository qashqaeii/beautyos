"""The reception-to-checkout handoff for a single salon day.

Reuses the appointment, invoice and payment sources of truth. No derived
financial amount is persisted in reception.
"""
from uuid import uuid4

from apps.appointments.models import Appointment
from apps.dashboard.role_services import appointment_payment_summary


def day_operations(*, salon, queue, limit=100):
    """Return an actionable, tenant-scoped day queue with payment visibility."""
    appointments = list(
        queue.select_related("customer", "staff", "service", "invoice_line", "package_use")
        .prefetch_related("payments__refunds")
        .order_by("start_at", "pk")[:limit]
    )
    rows = []
    summary = {
        "total": queue.count(),
        "pending": 0,
        "confirmed": 0,
        "checked_in": 0,
        "completed": 0,
        "settled": 0,
        "outstanding_toman": 0,
    }
    for appointment in appointments:
        # Preserve the same tenant as the reception source queryset; caller
        # cannot bring in a different salon's appointment.
        if appointment.salon_id != salon.pk:
            continue
        payment = appointment_payment_summary(appointment)
        invoice_line = getattr(appointment, "invoice_line", None)
        completed = appointment.status == Appointment.Status.COMPLETED
        summary["pending"] += appointment.status == Appointment.Status.PENDING
        summary["confirmed"] += appointment.status == Appointment.Status.CONFIRMED
        summary["checked_in"] += appointment.status == Appointment.Status.CHECKED_IN
        summary["completed"] += completed
        summary["settled"] += completed and payment["owed_toman"] <= 0
        if completed:
            summary["outstanding_toman"] += payment["owed_toman"]
        rows.append({
            "appointment": appointment,
            "payment": payment,
            "invoice_id": invoice_line.invoice_id if invoice_line else None,
            "can_confirm": appointment.status == Appointment.Status.PENDING,
            "can_checkin": appointment.status == Appointment.Status.CONFIRMED,
            "can_complete": appointment.status in (
                Appointment.Status.CONFIRMED, Appointment.Status.CHECKED_IN,
            ),
            "can_checkout": completed and invoice_line is None and not payment.get("covered_by_package", False),
            "invoice_key": str(uuid4()) if completed and invoice_line is None else None,
        })
    summary["truncated"] = summary["total"] > len(rows)
    return {"day_operations": rows, "day_operations_summary": summary}
