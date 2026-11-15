from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.commissions.models import CommissionEntry, CommissionRule


def _pick_rule(salon, staff, service):
    qs = CommissionRule.scoped(salon).filter(is_active=True).order_by("-created_at")
    return (
        qs.filter(staff=staff, service=service).first()
        or qs.filter(staff=staff, service__isnull=True).first()
        or qs.filter(staff__isnull=True, service=service).first()
        or qs.filter(staff__isnull=True, service__isnull=True).first()
    )


def recognize_commission_for_appointment(appointment: Appointment) -> CommissionEntry | None:
    if appointment.status != Appointment.Status.COMPLETED:
        return None
    if CommissionEntry.objects.filter(appointment=appointment).exists():
        return None
    rule = _pick_rule(appointment.salon, appointment.staff, appointment.service)
    base = appointment.price_toman or appointment.service.price_toman
    if rule:
        commission = rule.resolve_amount(base)
        snapshot = {
            "rule_id": str(rule.pk),
            "percent": str(rule.percent) if rule.percent is not None else None,
            "fixed_amount_toman": rule.fixed_amount_toman,
        }
    else:
        commission = int(Decimal(base) * Decimal("0.40"))
        snapshot = {"rule_id": None, "default_percent": "40"}

    return CommissionEntry.objects.create(
        salon=appointment.salon,
        appointment=appointment,
        staff=appointment.staff,
        base_amount_toman=base,
        commission_amount_toman=commission,
        rule_snapshot=snapshot,
    )


@transaction.atomic
def create_settlement(salon, staff, amount_toman: int, note: str = ""):
    from apps.commissions.models import CommissionSettlement

    settlement = CommissionSettlement.objects.create(
        salon=salon,
        staff=staff,
        amount_toman=amount_toman,
        note=note,
        settled_at=timezone.now(),
    )
    outstanding = CommissionEntry.scoped(salon).filter(
        staff=staff, status=CommissionEntry.Status.RECOGNIZED
    ).order_by("created_at")
    remaining = amount_toman
    for entry in outstanding:
        if remaining <= 0:
            break
        if entry.commission_amount_toman <= remaining:
            entry.status = CommissionEntry.Status.SETTLED
            entry.settlement = settlement
            entry.save(update_fields=["status", "settlement", "updated_at"])
            remaining -= entry.commission_amount_toman
    return settlement
