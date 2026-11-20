from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.retention.models import FollowUp
from apps.retention.services import sync_follow_up_queue, open_queue
from apps.salons.permissions_policy import P_MARKETING_MANAGE, has_permission
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role


def _parse_open_item_id(request) -> int | None:
    raw = request.GET.get("open")
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def follow_up_queue(request):
    if request.method == "POST" and request.POST.get("action") == "sync":
        sync_follow_up_queue(request.salon)
        messages.success(request, "صف پیگیری به‌روز شد.")
        return redirect("retention:queue")
    items = open_queue(request.salon)
    open_item_id = _parse_open_item_id(request)
    open_draft_note = ""
    if open_item_id:
        open_draft_note = request.session.get(f"followup_draft_{open_item_id}", "")
    return render(
        request,
        "retention/queue.html",
        {
            "items": items,
            "can_marketing":has_permission(request.membership,P_MARKETING_MANAGE),
            "snoozed_count":FollowUp.scoped(request.salon).filter(status=FollowUp.Status.SNOOZED,customer__is_deleted=False).count(),
            "queue_count": items.count(),
            "open_item_id": open_item_id,
            "open_draft_note": open_draft_note,
        },
    )


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
@transaction.atomic
def follow_up_done(request, pk):
    item = get_object_or_404(FollowUp.scoped(request.salon).select_for_update(), pk=pk)
    if request.method == "POST" and item.status == FollowUp.Status.OPEN:
        if request.POST.get("action")=="snooze":
            item.status=FollowUp.Status.SNOOZED
            item.next_follow_up_at=timezone.localdate()+timedelta(days=7)
            item.save(update_fields=["status","next_follow_up_at","updated_at"])
            messages.success(request,"پیگیری برای ۷ روز به تعویق افتاد.")
            return redirect("retention:queue")
        raw_note = request.POST.get("result_note", "")
        note = raw_note.strip()[:2000]
        if not note:
            messages.error(request, "نتیجه تماس یا اقدام بعدی را وارد کنید.")
            request.session[f"followup_draft_{pk}"] = raw_note
            return redirect(f"{reverse('retention:queue')}?open={pk}")
        item.status = FollowUp.Status.DONE
        item.result_note = note
        item.save(update_fields=["status", "result_note", "updated_at"])
        request.session.pop(f"followup_draft_{pk}", None)
        messages.success(request, "پیگیری ثبت شد.")
    return redirect("retention:queue")
