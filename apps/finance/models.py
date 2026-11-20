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

    invoice = models.ForeignKey("finance.Invoice", on_delete=models.PROTECT, null=True, blank=True, related_name="payments")
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


class Invoice(TenantModelMixin, TimeStampedModel):
    """Immutable issue-time snapshot; Payment remains the receipt ledger."""
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="invoices")
    customer_name = models.CharField(max_length=200)
    request_key = models.UUIDField()
    request_digest = models.CharField(max_length=64)
    gross_toman = models.BigIntegerField()
    prior_discount_toman = models.BigIntegerField(default=0)
    prior_paid_toman = models.BigIntegerField(default=0)
    discount_toman = models.BigIntegerField(default=0)
    received_toman = models.BigIntegerField(default=0)
    balance_at_issue_toman = models.BigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["salon", "request_key"], name="finance_invoice_request_key")]


class InvoiceLine(TenantModelMixin, TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="lines")
    appointment = models.OneToOneField("appointments.Appointment", on_delete=models.PROTECT, related_name="invoice_line")
    service_name = models.CharField(max_length=120)
    staff_name = models.CharField(max_length=200)
    gross_toman = models.BigIntegerField()
    prior_discount_toman = models.BigIntegerField(default=0)
    prior_paid_toman = models.BigIntegerField(default=0)
    discount_toman = models.BigIntegerField(default=0)
    received_toman = models.BigIntegerField(default=0)
    balance_at_issue_toman = models.BigIntegerField(default=0)


class CashClose(TenantModelMixin, TimeStampedModel):
    """Immutable reconciliation of recorded receipts and manually counted cash."""
    day = models.DateField()
    closed_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    opening_toman = models.BigIntegerField()
    other_in_toman = models.BigIntegerField(default=0)
    cash_out_toman = models.BigIntegerField(default=0)
    cash_received_toman = models.BigIntegerField(default=0)
    card_received_toman = models.BigIntegerField(default=0)
    transfer_received_toman = models.BigIntegerField(default=0)
    expected_toman = models.BigIntegerField()
    counted_toman = models.BigIntegerField()
    difference_toman = models.BigIntegerField()
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["salon", "day"], name="finance_cashclose_day")]
