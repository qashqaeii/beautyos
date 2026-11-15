from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.tenant import TenantModelMixin


class Payment(TenantModelMixin, TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "نقد"
        CARD = "card", "کارت"
        TRANSFER = "transfer", "انتقال"

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        PARTIAL = "partial", "بخشی"
        PAID = "paid", "تسویه"
        REFUNDED = "refunded", "استرداد"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    total_amount_toman = models.BigIntegerField(default=0)
    discount_toman = models.BigIntegerField(default=0)
    paid_amount_toman = models.BigIntegerField(default=0)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PAID)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["salon", "-created_at"]),
            models.Index(fields=["salon", "status"]),
        ]

    @property
    def balance_toman(self):
        return max(self.total_amount_toman - self.discount_toman - self.paid_amount_toman, 0)


class SalonDebt(TenantModelMixin, TimeStampedModel):
    class CreditorType(models.TextChoices):
        BRAND = "brand", "برند"
        COMPANY = "company", "شرکت"
        PERSON = "person", "فرد"

    creditor_name = models.CharField(max_length=200)
    creditor_type = models.CharField(max_length=20, choices=CreditorType.choices, default=CreditorType.COMPANY)
    principal_toman = models.BigIntegerField()
    paid_toman = models.BigIntegerField(default=0)
    due_date = models.DateField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)
    note = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["salon", "is_closed", "-created_at"]),
        ]

    @property
    def balance_toman(self) -> int:
        return max(int(self.principal_toman) - int(self.paid_toman), 0)


class SalonDebtPayment(TenantModelMixin, TimeStampedModel):
    debt = models.ForeignKey(SalonDebt, on_delete=models.CASCADE, related_name="payments")
    amount_toman = models.BigIntegerField()
    note = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["salon", "debt", "-created_at"])]
