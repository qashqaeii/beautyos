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


class SubscriptionPlan(TimeStampedModel):
    """Commercial offering of BeautyOS, unrelated to salon service prices."""

    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    price_toman = models.PositiveBigIntegerField(default=0)
    period_days = models.PositiveSmallIntegerField(default=30)
    trial_days = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=False, db_index=True)
    description = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["price_toman", "pk"]
        verbose_name = "پلن اشتراک پلتفرم"
        verbose_name_plural = "پلن‌های اشتراک پلتفرم"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.period_days < 1:
            raise ValidationError({"period_days": "دوره پلن باید حداقل یک روز باشد."})

    def __str__(self):
        return self.name


class SalonSubscription(TimeStampedModel):
    """One subscription state per salon. This model does not charge money."""

    class Status(models.TextChoices):
        TRIAL = "trial", "آزمایشی"
        ACTIVE = "active", "فعال"
        PAST_DUE = "past_due", "در انتظار پرداخت"
        EXPIRED = "expired", "منقضی"
        CANCELED = "canceled", "لغوشده"

    salon = models.OneToOneField(
        "salons.Salon", on_delete=models.CASCADE, related_name="platform_subscription",
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIAL, db_index=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    # No payment status or entitlement gate until provider-verification is implemented.

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "اشتراک سالن در BeautyOS"
        verbose_name_plural = "اشتراک سالن‌ها در BeautyOS"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "زمان پایان باید بعد از شروع اشتراک باشد."
        if self.trial_ends_at and self.starts_at and self.trial_ends_at <= self.starts_at:
            errors["trial_ends_at"] = "پایان دوره آزمایشی باید بعد از شروع باشد."
        if self.trial_ends_at and self.ends_at and self.trial_ends_at > self.ends_at:
            errors["trial_ends_at"] = "پایان دوره آزمایشی نباید پس از پایان اشتراک باشد."
        if self.status == self.Status.TRIAL and not self.trial_ends_at:
            errors["trial_ends_at"] = "برای وضعیت آزمایشی تاریخ پایان دوره لازم است."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.salon} — {self.plan}"


class PlatformActivityEvent(models.Model):
    """Privacy-minimal, immutable product-usage fact; separate from security AuditLog.

    Only an allowlisted event name and numeric count are stored. Never store customer
    names, phone numbers, appointment notes, or other salon-private payloads.
    """

    class Kind(models.TextChoices):
        APPOINTMENT_CREATED = "appointment_created", "ثبت نوبت"
        APPOINTMENT_COMPLETED = "appointment_completed", "تکمیل نوبت"
        INVOICE_CREATED = "invoice_created", "صدور فاکتور"
        CUSTOMER_CREATED = "customer_created", "ثبت مشتری"
        STAFF_CREATED = "staff_created", "افزودن متخصص"
        PUBLIC_BOOKING_ENABLED = "public_booking_enabled", "فعال‌سازی رزرو آنلاین"

    salon = models.ForeignKey(
        "salons.Salon", on_delete=models.CASCADE, related_name="platform_activity_events",
    )
    kind = models.CharField(max_length=40, choices=Kind.choices)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    count = models.PositiveIntegerField(default=1)
    # Optional idempotency key from the originating business operation.
    dedupe_key = models.CharField(max_length=120, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["-occurred_at", "-pk"]
        indexes = [
            models.Index(fields=["salon", "-occurred_at"], name="plat_event_salon_date_idx"),
            models.Index(fields=["kind", "-occurred_at"], name="plat_event_kind_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(count__gte=1), name="plat_event_count_positive"),
        ]
