from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.tenant import TenantModelMixin


class CommissionRule(TenantModelMixin, TimeStampedModel):
    staff = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="commission_rules",
    )
    service = models.ForeignKey(
        "services.Service",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="commission_rules",
    )
    percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    fixed_amount_toman = models.BigIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    name = models.CharField(max_length=120, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["salon", "is_active"]),
            models.Index(fields=["salon", "staff", "service"]),
        ]

    def resolve_amount(self, base_amount_toman: int) -> int:
        if self.fixed_amount_toman is not None:
            return int(self.fixed_amount_toman)
        if self.percent is not None:
            return int(Decimal(base_amount_toman) * (self.percent / Decimal("100")))
        return 0


class CommissionEntry(TenantModelMixin, TimeStampedModel):
    class Status(models.TextChoices):
        RECOGNIZED = "recognized", "شناسایی‌شده"
        SETTLED = "settled", "تسویه‌شده"
        VOID = "void", "باطل"

    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        related_name="commission_entry",
    )
    staff = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.PROTECT,
        related_name="commission_entries",
    )
    base_amount_toman = models.BigIntegerField()
    commission_amount_toman = models.BigIntegerField()
    rule_snapshot = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECOGNIZED)
    settlement = models.ForeignKey(
        "CommissionSettlement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entries",
    )

    class Meta:
        indexes = [models.Index(fields=["salon", "staff", "status", "-created_at"])]


class CommissionSettlement(TenantModelMixin, TimeStampedModel):
    staff = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.PROTECT,
        related_name="commission_settlements",
    )
    amount_toman = models.BigIntegerField()
    note = models.TextField(blank=True)
    settled_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["salon", "staff", "-settled_at"])]
