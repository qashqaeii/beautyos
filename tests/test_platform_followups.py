"""Follow-up ordering uses transparent operational signals."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.platform_admin.followups import followup_queue
from apps.platform_admin.models import SupportTicket


@pytest.mark.django_db
def test_followup_queue_includes_open_ticket_and_ignores_resolved(salon, owner_membership):
    SupportTicket.objects.create(
        salon=salon, opened_by=owner_membership.user,
        title="درخواست باز", status=SupportTicket.Status.OPEN,
    )
    result = followup_queue()
    entry = next(item for item in result["items"] if item["salon"].pk == salon.pk)
    assert "پشتیبانی باز" in entry["reasons"]
    assert entry["open_tickets"] == 1
    SupportTicket.objects.filter(salon=salon).update(status=SupportTicket.Status.RESOLVED)
    result = followup_queue()
    entry = next((item for item in result["items"] if item["salon"].pk == salon.pk), None)
    assert entry is None or entry["open_tickets"] == 0


@pytest.mark.django_db
def test_followup_queue_limits_rows_and_preserves_total(salon, owner_membership):
    SupportTicket.objects.create(
        salon=salon, opened_by=owner_membership.user,
        title="درخواست", status=SupportTicket.Status.IN_PROGRESS,
    )
    assert followup_queue(limit=0)["items"] == []
    assert followup_queue(limit=0)["total"] >= 1
