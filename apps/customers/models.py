from django.conf import settings
from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel
from apps.core.tenant import TenantModelMixin


class CustomerTag(TenantModelMixin, TimeStampedModel):
    name = models.CharField(max_length=40)
    color = models.CharField(max_length=7, default="#A58BB9")
    is_system = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["salon", "name"], name="unique_tag_per_salon"),
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name


class Customer(TenantModelMixin, SoftDeleteModel, TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "جدید"
        ACTIVE = "active", "فعال"
        INACTIVE = "inactive", "غیرفعال"
        VIP = "vip", "ویژه (VIP)"

    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=16, db_index=True)
    email = models.EmailField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    avatar = models.ImageField(upload_to="customers/avatars/", blank=True, null=True)
    notes_count = models.PositiveIntegerField(default=0)
    is_vip = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    first_visit_at = models.DateTimeField(null=True, blank=True)
    last_visit_at = models.DateTimeField(null=True, blank=True)
    total_visits = models.PositiveIntegerField(default=0)
    total_spent_toman = models.BigIntegerField(default=0)
    tags = models.ManyToManyField(CustomerTag, blank=True, related_name="customers")
    marketing_consent = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["salon", "phone"]),
            models.Index(fields=["salon", "-last_visit_at"]),
            models.Index(fields=["salon", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["salon", "phone"],
                condition=models.Q(is_deleted=False),
                name="unique_customer_phone_per_salon",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name

    @property
    def initials(self) -> str:
        name = (self.full_name or "").strip()
        if not name:
            return "؟"
        parts = name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[-1][0]}"
        if len(name) >= 2:
            return name[:2]
        return name[0]

    @property
    def total_spent(self):
        return self.total_spent_toman


class CustomerNote(TenantModelMixin, TimeStampedModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="customer_notes",
    )
    body = models.TextField()

    class Meta:
        ordering = ["-created_at"]


class CustomerActivity(TenantModelMixin, TimeStampedModel):
    class ActivityType(models.TextChoices):
        CREATED = "created", "ایجاد مشتری"
        UPDATED = "updated", "ویرایش"
        NOTE = "note", "یادداشت"
        APPOINTMENT = "appointment", "نوبت"
        PAYMENT = "payment", "پرداخت"
        FOLLOW_UP = "follow_up", "پیگیری"
        ARCHIVED = "archived", "آرشیو"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=32, choices=ActivityType.choices)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    entity_type = models.CharField(max_length=64, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["salon", "customer", "-created_at"])]
