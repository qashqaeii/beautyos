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
    cycle_key = models.CharField(max_length=64, blank=True, default="")
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
        constraints = [models.UniqueConstraint(fields=["salon","customer","cycle_key"],condition=~models.Q(cycle_key=""),name="retention_unique_followup_cycle")]


class Campaign(TenantModelMixin, TimeStampedModel):
    class Segment(models.TextChoices):
        ACTIVE = "active", "مشتریان فعال"
        AT_RISK = "at_risk", "نیازمند پیگیری"
        INACTIVE = "inactive", "مشتریان غیرفعال"
        NEW = "new", "بدون مراجعه انجام‌شده"
        VIP = "vip", "مشتریان ویژه"
        BIRTHDAY = "birthday", "تولد این ماه"
    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        PREPARED = "prepared", "مخاطبان آماده"
        CANCELLED = "cancelled", "لغوشده"
    title = models.CharField(max_length=100)
    segment = models.CharField(max_length=16,choices=Segment.choices)
    message = models.CharField(max_length=480)
    status = models.CharField(max_length=16,choices=Status.choices,default=Status.DRAFT)
    request_key = models.UUIDField()
    prepared_at = models.DateTimeField(null=True,blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["salon","request_key"],name="retention_campaign_request")]


class CampaignRecipient(TenantModelMixin, TimeStampedModel):
    campaign = models.ForeignKey(Campaign,on_delete=models.PROTECT,related_name="recipients")
    customer = models.ForeignKey("customers.Customer",on_delete=models.PROTECT,related_name="campaign_recipients")
    message_snapshot = models.CharField(max_length=480)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["campaign","customer"],name="retention_campaign_customer")]
