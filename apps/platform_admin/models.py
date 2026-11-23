from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class SupportTicket(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "باز"
        IN_PROGRESS = "in_progress", "در حال پیگیری"
        RESOLVED = "resolved", "حل‌شده"
        CLOSED = "closed", "بسته"

    class Category(models.TextChoices):
        GENERAL = "general", "راهنمایی"
        TECHNICAL = "technical", "فنی"
        FINANCIAL = "financial", "مالی و اشتراک"
        SUGGESTION = "suggestion", "پیشنهاد"

    class Priority(models.TextChoices):
        NORMAL = "normal", "عادی"
        HIGH = "high", "بالا"
        URGENT = "urgent", "فوری"

    salon = models.ForeignKey("salons.Salon", on_delete=models.CASCADE, related_name="support_tickets")
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="support_tickets_created",
    )
    title = models.CharField(max_length=180)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.NORMAL)
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_activity_at", "-pk"]
        indexes = [
            models.Index(fields=["salon", "status", "-last_activity_at"], name="plat_ticket_salon_status_idx"),
            models.Index(fields=["status", "-last_activity_at"], name="plat_ticket_status_idx"),
        ]

    def __str__(self):
        return self.title


class SupportMessage(TimeStampedModel):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="support_messages",
    )
    body = models.TextField(max_length=5000)
    is_internal = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"پیام {self.pk} در درخواست {self.ticket_id}"
