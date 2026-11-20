from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
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


def _active_entry_qs(appointment: Appointment):
    return CommissionEntry.objects.filter(appointment=appointment).exclude(status=CommissionEntry.Status.VOID)


@transaction.atomic
def recognize_commission_for_appointment(appointment: Appointment) -> CommissionEntry | None:
    if appointment.status != Appointment.Status.COMPLETED:
        return None
    existing = (
        _active_entry_qs(appointment).select_for_update().first()
    )
    if existing:
        return existing

    rule = _pick_rule(appointment.salon, appointment.staff, appointment.service)
    base = appointment.price_toman or appointment.service.price_toman
    from apps.finance.periods import agreement_for
    agreement=agreement_for(appointment.salon,appointment.staff_id,timezone.localdate(appointment.completed_at or timezone.now()))
    if agreement and agreement.mode in ("salary","rent"):
        commission=0
        snapshot={"agreement_id":agreement.pk,"mode":agreement.mode}
    elif rule:
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
def reverse_commission_for_appointment(appointment: Appointment) -> CommissionEntry | None:
    entry = (
        _active_entry_qs(appointment).select_for_update().first()
    )
    if entry is None:
        return None
    existing = entry.reversal_entries.exclude(status=CommissionEntry.Status.VOID).first()
    if existing:
        return existing

    amount = int(entry.commission_amount_toman)
    if amount < 0:
        raise ValidationError("برگشت پورسانت نامعتبر است.")

    # Void unpaid entitlement, but preserve the actual cash already paid.
    paid = amount if entry.status == CommissionEntry.Status.SETTLED else int(entry.settled_amount_toman)
    if entry.status == CommissionEntry.Status.RECOGNIZED:
        entry.status = CommissionEntry.Status.VOID
        entry.save(update_fields=["status", "updated_at"])
        if not paid:
            return entry

    if paid > 0:
        return CommissionEntry.objects.create(
            salon=entry.salon,
            appointment=None,
            staff=entry.staff,
            base_amount_toman=0,
            commission_amount_toman=-paid,
            rule_snapshot={"reversal": True, "source_entry_id": entry.pk},
            status=CommissionEntry.Status.RECOGNIZED,
            reverses_entry=entry,
        )

    return None


def net_commission_effect_for_appointment(appointment: Appointment) -> int:
    """Net commission impact (primary entry + reversals) for one appointment."""
    primary = CommissionEntry.objects.filter(appointment=appointment).first()
    if primary is None:
        return 0
    total = (int(primary.settled_amount_toman) if primary.status == CommissionEntry.Status.VOID
             else int(primary.commission_amount_toman))
    for rev in primary.reversal_entries.all():
        if rev.status != CommissionEntry.Status.VOID:
            total += int(rev.commission_amount_toman)
    return total


def audit_appointment_commission_consistency(*, salon=None) -> list[dict]:
    """Read-only: cancelled/completed appointments with inconsistent commission state."""
    from apps.appointments.models import Appointment

    qs = Appointment.objects.all() if salon is None else Appointment.scoped(salon)
    issues = []
    for appt in qs.filter(status=Appointment.Status.CANCELLED):
        primary = CommissionEntry.objects.filter(appointment=appt).first()
        if primary and net_commission_effect_for_appointment(appt) != 0:
            issues.append(
                {
                    "appointment_id": appt.pk,
                    "status": appt.status,
                    "net_commission": net_commission_effect_for_appointment(appt),
                    "entry_status": primary.status,
                }
            )
    for appt in qs.filter(status=Appointment.Status.COMPLETED):
        if not _active_entry_qs(appt).exists():
            issues.append({"appointment_id": appt.pk, "status": appt.status, "missing_commission": True})
    return issues


def staff_outstanding_commission(*, salon, staff) -> int:
    entries = CommissionEntry.scoped(salon).filter(
        staff=staff,
        status=CommissionEntry.Status.RECOGNIZED,
    )
    total = 0
    for entry in entries:
        total += int(entry.commission_amount_toman) - int(entry.settled_amount_toman)
    return max(0, total)


@transaction.atomic
def create_settlement(salon, staff, amount_toman: int, note: str = ""):
    from apps.commissions.models import CommissionSettlement
    from apps.staff.models import StaffProfile

    if staff.salon_id != salon.pk:
        raise ValidationError("متخصص متعلق به این سالن نیست.")
    StaffProfile.scoped(salon).select_for_update().get(pk=staff.pk)
    if amount_toman <= 0:
        raise ValidationError("مبلغ تسویه باید بزرگ‌تر از صفر باشد.")

    outstanding = list(
        CommissionEntry.scoped(salon)
        .select_for_update()
        .filter(staff=staff, status=CommissionEntry.Status.RECOGNIZED)
        .order_by("created_at")
    )
    due_total = max(0, sum(int(e.commission_amount_toman) - int(e.settled_amount_toman) for e in outstanding))
    if amount_toman > due_total:
        raise ValidationError(f"مبلغ تسویه بیش از مانده قابل پرداخت است. مانده: {due_total} تومان.")

    settlement = CommissionSettlement.objects.create(
        salon=salon,
        staff=staff,
        amount_toman=amount_toman,
        note=note,
        settled_at=timezone.now(),
    )
    # Existing reversal credits offset future entitlement before additional cash.
    remaining = amount_toman
    for entry in outstanding:
        due = int(entry.commission_amount_toman) - int(entry.settled_amount_toman)
        if due < 0:
            remaining += -due
            entry.settled_amount_toman = entry.commission_amount_toman
            entry.status = CommissionEntry.Status.SETTLED
            entry.settlement = settlement
            entry.save(update_fields=["settled_amount_toman", "status", "settlement", "updated_at"])
    for entry in outstanding:
        if remaining <= 0:
            break
        due = int(entry.commission_amount_toman) - int(entry.settled_amount_toman)
        if due <= 0:
            continue
        apply = min(due, remaining)
        entry.settled_amount_toman = int(entry.settled_amount_toman) + apply
        update_fields = ["settled_amount_toman", "updated_at"]
        if entry.settled_amount_toman >= entry.commission_amount_toman:
            entry.status = CommissionEntry.Status.SETTLED
            entry.settlement = settlement
            update_fields.extend(["status", "settlement"])
        entry.save(update_fields=update_fields)
        remaining -= apply
    if remaining:
        raise ValidationError("مانده پورسانت تغییر کرده است؛ دوباره تلاش کنید.")
    return settlement