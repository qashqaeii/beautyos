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


class Refund(TenantModelMixin, TimeStampedModel):
    payment = models.ForeignKey("finance.Payment", on_delete=models.PROTECT, related_name="refunds")
    request_key = models.UUIDField()
    amount_toman = models.BigIntegerField()
    reason = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["salon", "request_key"], name="finance_refund_request_key"),
            models.CheckConstraint(condition=models.Q(amount_toman__gt=0), name="finance_refund_positive"),
        ]


class FinancialAccount(TenantModelMixin, TimeStampedModel):
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=[("cash", "صندوق نقدی"), ("bank", "حساب بانکی")])
    opening_toman = models.BigIntegerField(default=0)
    opening_day = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["salon", "name"], name="finance_account_name"),
        ]


class AccountMovement(TenantModelMixin, TimeStampedModel):
    from_account = models.ForeignKey("finance.FinancialAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="outgoing")
    to_account = models.ForeignKey("finance.FinancialAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="incoming")
    amount_toman = models.BigIntegerField()
    day = models.DateField()
    source_kind = models.CharField(max_length=24, blank=True)
    source_id = models.BigIntegerField(null=True, blank=True)
    request_key = models.UUIDField()
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["salon", "request_key"], name="finance_movement_request_key"),
            models.UniqueConstraint(fields=["salon", "source_kind", "source_id"], condition=models.Q(source_id__isnull=False), name="finance_movement_source"),
            models.CheckConstraint(condition=models.Q(amount_toman__gt=0), name="finance_movement_positive"),
            models.CheckConstraint(condition=(models.Q(from_account__isnull=False)|models.Q(to_account__isnull=False)) & ~(models.Q(from_account=models.F("to_account")) & models.Q(from_account__isnull=False) & models.Q(to_account__isnull=False)), name="finance_movement_accounts"),
        ]


class StaffAgreement(TenantModelMixin, TimeStampedModel):
    staff = models.ForeignKey("staff.StaffProfile", on_delete=models.PROTECT, related_name="finance_agreements")
    effective_month = models.DateField()
    mode = models.CharField(max_length=12, choices=[("commission","درصدی"),("salary","حقوق ثابت"),("hybrid","ترکیبی"),("rent","اجاره جایگاه")])
    monthly_toman = models.BigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["salon","staff","effective_month"],name="finance_staff_agreement_month")]


class StaffPeriod(TenantModelMixin, TimeStampedModel):
    staff = models.ForeignKey("staff.StaffProfile", on_delete=models.PROTECT, related_name="finance_periods")
    agreement = models.ForeignKey("finance.StaffAgreement", on_delete=models.PROTECT, related_name="periods")
    month = models.DateField()
    kind = models.CharField(max_length=10, choices=[("salary","حقوق"),("rent","اجاره جایگاه")])
    amount_toman = models.BigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["salon","staff","month"],name="finance_staff_period_month")]


class StaffPeriodPayment(TenantModelMixin, TimeStampedModel):
    period = models.ForeignKey("finance.StaffPeriod", on_delete=models.PROTECT, related_name="payments")
    kind = models.CharField(max_length=12, choices=[("advance","مساعده حقوق"),("settlement","تسویه حقوق"),("rent","دریافت اجاره")])
    amount_toman = models.BigIntegerField()
    request_key = models.UUIDField()
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["salon","request_key"],name="finance_staff_payment_request"), models.CheckConstraint(condition=models.Q(amount_toman__gt=0),name="finance_staff_payment_positive")]


class RecurringExpense(TenantModelMixin, TimeStampedModel):
    title = models.CharField(max_length=120)
    category = models.CharField(max_length=20)
    amount_toman = models.BigIntegerField()
    next_due = models.DateField()
    day_of_month = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)


class ExpenseOccurrence(TenantModelMixin, TimeStampedModel):
    schedule = models.ForeignKey("finance.RecurringExpense", on_delete=models.PROTECT, related_name="occurrences")
    due_day = models.DateField()
    expense = models.OneToOneField("expenses.Expense", on_delete=models.PROTECT, related_name="recurring_occurrence")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["salon","schedule","due_day"],name="finance_expense_occurrence_day")]


class ProductSale(TenantModelMixin, TimeStampedModel):
    payment = models.OneToOneField("finance.Payment", on_delete=models.PROTECT, related_name="product_sale")
    item = models.ForeignKey("inventory.InventoryItem", on_delete=models.PROTECT, related_name="finance_sales")
    movement = models.OneToOneField("inventory.StockMovement", on_delete=models.PROTECT, related_name="product_sale")
    item_name = models.CharField(max_length=120)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price_toman = models.BigIntegerField()
    unit_cost_toman = models.BigIntegerField()
    revenue_toman = models.BigIntegerField()
    cost_toman = models.BigIntegerField()
    request_key = models.UUIDField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["salon","request_key"],name="finance_product_sale_request")]


class ProductReturn(TenantModelMixin, TimeStampedModel):
    sale = models.OneToOneField("finance.ProductSale", on_delete=models.PROTECT, related_name="return_record")
    refund = models.OneToOneField("finance.Refund", on_delete=models.PROTECT, related_name="product_return")
    movement = models.OneToOneField("inventory.StockMovement", on_delete=models.PROTECT, related_name="product_return")


class MaterialCost(TenantModelMixin, TimeStampedModel):
    movement = models.OneToOneField("inventory.StockMovement", on_delete=models.PROTECT, related_name="material_cost")
    appointment = models.ForeignKey("appointments.Appointment", on_delete=models.PROTECT, related_name="material_costs")
    item_name = models.CharField(max_length=120)
    unit_cost_toman = models.BigIntegerField()
    cost_toman = models.BigIntegerField()
    request_key = models.UUIDField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["salon","request_key"],name="finance_material_request")]
