from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from apps.inventory.models import InventoryCategory, InventoryItem, StockMovement


@transaction.atomic
def create_inventory_item(
    *,
    salon,
    name: str,
    unit: str,
    minimum_quantity: Decimal,
    category: InventoryCategory | None = None,
    initial_quantity: Decimal | None = None,
    note: str = "",
) -> InventoryItem:
    item = InventoryItem.objects.create(
        salon=salon,
        name=name,
        unit=unit,
        category=category,
        minimum_quantity=minimum_quantity,
        quantity=Decimal(0),
    )
    qty = initial_quantity or Decimal(0)
    if qty > 0:
        apply_movement(
            salon=salon,
            item=item,
            kind=StockMovement.Kind.IN,
            quantity=qty,
            note=note or "موجودی اولیه",
        )
    return item


@transaction.atomic
def apply_movement(*, salon, item: InventoryItem, kind: str, quantity: Decimal, note: str = "", appointment=None) -> StockMovement:
    if quantity <= 0:
        raise ValidationError("مقدار باید مثبت باشد.")
    if kind == StockMovement.Kind.OUT:
        if item.quantity - quantity < 0:
            raise ValidationError("موجودی کافی نیست.")
        if appointment and StockMovement.objects.filter(appointment=appointment, item=item, kind=StockMovement.Kind.OUT).exists():
            raise ValidationError("مصرف این کالا برای نوبت قبلاً ثبت شده.")
        InventoryItem.objects.filter(pk=item.pk).update(quantity=F("quantity") - quantity)
    elif kind == StockMovement.Kind.IN:
        InventoryItem.objects.filter(pk=item.pk).update(quantity=F("quantity") + quantity)
    else:
        InventoryItem.objects.filter(pk=item.pk).update(quantity=quantity)
    item.refresh_from_db(fields=["quantity"])
    return StockMovement.objects.create(
        salon=salon,
        item=item,
        kind=kind,
        quantity=quantity,
        note=note,
        appointment=appointment,
    )
