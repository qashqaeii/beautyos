"""Fail-closed customer SMS dispatch, reconciliation and per-salon throttling."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.retention.automation import suppression_reason
from apps.retention.models import AutomationMessage, AutomationPolicy
from apps.retention.transport import KavenegarTransport, ProviderRejected, ready
from apps.salons.models import Salon, SalonSettings

MARKETING_KINDS = ("birthday", "winback", "campaign")
IN_FLIGHT = ("claimed", "accepted", "delivered", "unknown")


def _claim(message_id, now):
    """Serialize claim and salon-wide limits. No HTTP request within a DB lock."""
    salon_id = AutomationMessage.objects.filter(pk=message_id).values_list("salon_id", flat=True).first()
    if not salon_id:
        return None
    with transaction.atomic():
        salon = Salon.objects.select_for_update().get(pk=salon_id)
        row = (AutomationMessage.scoped(salon).select_for_update()
               .select_related("salon", "customer", "appointment", "followup", "campaign_recipient__campaign")
               .filter(pk=message_id).first())
        if not row or row.status != "pending" or row.due_at > now:
            return None
        policy = AutomationPolicy.scoped(salon).first()
        configuration = SalonSettings.objects.filter(salon=salon).first()
        reason = suppression_reason(row, policy, configuration, now)
        if reason:
            row.status = "skipped"
            row.reason = reason
            row.save(update_fields=["status", "reason", "updated_at"])
            return None
        if row.kind in MARKETING_KINDS:
            since = now - timedelta(hours=24)
            active = AutomationMessage.scoped(salon).filter(
                kind__in=MARKETING_KINDS, status__in=IN_FLIGHT,
                attempted_at__gte=since,
            )
            cap = max(1, min(policy.daily_marketing_cap if policy else 30, 500))
            if active.count() >= cap:
                return None
            if active.filter(customer_id=row.customer_id).exclude(pk=row.pk).exists():
                return None
        row.status = "claimed"
        row.attempted_at = now
        row.reason = ""
        row.save(update_fields=["status", "attempted_at", "reason", "updated_at"])
        return row


def dispatch_due(salon, now=None, limit=100, transport=None):
    """Each durable source event is sent at most once, including on timeouts."""
    if not getattr(settings, "BEAUTYOS_AUTOMATION_SEND_ENABLED", False):
        return {"accepted": 0, "failed": 0, "unknown": 0, "disabled": True}
    if transport is None:
        if not ready():
            return {"accepted": 0, "failed": 0, "unknown": 0, "disabled": True}
        transport = KavenegarTransport()
    now = now or timezone.now()
    ids = list(AutomationMessage.scoped(salon).filter(
        status="pending", due_at__lte=now,
    ).order_by("due_at", "pk").values_list("pk", flat=True)[:max(1, min(limit, 500))])
    result = {"accepted": 0, "failed": 0, "unknown": 0, "disabled": False}
    for pk in ids:
        row = _claim(pk, now)
        if row is None:
            continue
        try:
            provider_message_id = transport.send(row, row.customer.phone)
            if not provider_message_id:
                raise ValueError("Provider did not confirm an id")
        except ProviderRejected:
            outcome, reason, provider_message_id = "failed", "درگاه درخواست را رد کرد.", ""
        except Exception:
            # Network timeouts/crashes can happen after the provider accepts.
            # Never automatically retry the same localid or create a new one.
            outcome, reason, provider_message_id = "unknown", "پاسخ ارسال نامشخص؛ نیازمند استعلام.", ""
        else:
            outcome, reason = "accepted", ""
        AutomationMessage.scoped(salon).filter(pk=pk, status="claimed").update(
            status=outcome, reason=reason, provider_message_id=str(provider_message_id),
            updated_at=timezone.now(),
        )
        AuditLog.objects.create(
            salon=salon, actor=None, action=AuditLog.Action.UPDATE,
            entity_type="automation_delivery", entity_id=str(pk),
            message=f"نتیجه پذیرش پیام: {outcome}", metadata={"kind": row.kind},
        )
        result[outcome] += 1
    return result


def reconcile_delivery(salon, now=None, limit=100, transport=None):
    """Poll confirmed provider ids or the original localid; never resend."""
    if not getattr(settings, "BEAUTYOS_AUTOMATION_SEND_ENABLED", False):
        return 0
    if transport is None:
        if not ready():
            return 0
        transport = KavenegarTransport()
    now = now or timezone.now()
    ids = list(AutomationMessage.scoped(salon).filter(
        status__in=("claimed", "accepted", "unknown"),
        attempted_at__lte=now - timedelta(minutes=5),
    ).order_by("last_checked_at", "pk").values_list("pk", flat=True)[:max(1, min(limit, 500))])
    changed = 0
    for pk in ids:
        row = AutomationMessage.scoped(salon).filter(pk=pk).first()
        if not row or row.status not in ("claimed", "accepted", "unknown"):
            continue
        try:
            outcome, provider_id = transport.lookup(row)
        except Exception:
            outcome, provider_id = None, ""
        next_status = outcome if outcome in ("accepted", "delivered", "failed") else ("unknown" if row.status == "claimed" else row.status)
        updated = AutomationMessage.scoped(salon).filter(pk=pk, status=row.status).update(
            status=next_status,
            provider_message_id=str(provider_id or row.provider_message_id),
            last_checked_at=now,
            updated_at=now,
        )
        if updated and next_status != row.status:
            changed += 1
    return changed
