from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.tenant import TenantModelMixin


class FollowUp(TenantModelMixin, TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "باز"
        DONE = "done", "انجام شد"
        SNOOZED = "snoozed", "به‌تعویق"

    class Priority(models.TextChoices):
        LOW = "low", "عادی"
        MEDIUM = "medium", "متوسط"
        HIGH = "high", "بالا"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="follow_ups",
    )
    reason = models.CharField(max_length=120)
    days_since_visit = models.PositiveIntegerField(default=0)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    result_note = models.TextField(blank=True)
    next_follow_up_at = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_ups",
    )

    class Meta:
        indexes = [models.Index(fields=["salon", "status", "-created_at"])]
