from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.tenant import TenantModelMixin


class InventoryCategory(TenantModelMixin, TimeStampedModel):
    name = models.CharField(max_length=80)

    class Meta:
        indexes = [models.Index(fields=["salon", "name"])]
        constraints = [
            models.UniqueConstraint(
                fields=["salon", "name"],
                name="unique_inventory_category_per_salon",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class InventoryItem(TenantModelMixin, TimeStampedModel):
    class Unit(models.TextChoices):
        PIECE = "عدد", "عدد"
        PACK = "بسته", "بسته"
        GRAM = "گرم", "گرم"
        ML = "میلی‌لیتر", "میلی‌لیتر"

    name = models.CharField(max_length=120)
    category = models.ForeignKey(
        InventoryCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    unit = models.CharField(max_length=20, choices=Unit.choices, default=Unit.PIECE)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    minimum_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    purchase_price_toman = models.BigIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["salon", "name"])]

    @property
    def is_low_stock(self) -> bool:
        return self.quantity > 0 and self.quantity <= self.minimum_quantity

    @property
    def is_out_of_stock(self) -> bool:
        return self.quantity <= 0

    @property
    def stock_status(self) -> str:
        if self.is_out_of_stock:
            return "out"
        if self.is_low_stock:
            return "low"
        return "ok"


class StockMovement(TenantModelMixin, TimeStampedModel):
    class Kind(models.TextChoices):
        IN = "in", "ورود"
        OUT = "out", "مصرف"
        ADJUST = "adjust", "اصلاح"

    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    class Meta:
        indexes = [models.Index(fields=["salon", "item", "-created_at"])]
