from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

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
def apply_movement(
    *,
    salon,
    item: InventoryItem,
    kind: str,
    quantity: Decimal,
    note: str = "",
    appointment=None,
) -> StockMovement:
    if quantity <= 0:
        raise ValidationError("مقدار باید مثبت باشد.")

    locked = InventoryItem.objects.select_for_update().get(pk=item.pk, salon=salon)

    if kind == StockMovement.Kind.OUT:
        if appointment and StockMovement.objects.filter(
            appointment=appointment, item=locked, kind=StockMovement.Kind.OUT
        ).exists():
            raise ValidationError("مصرف این کالا برای نوبت قبلاً ثبت شده.")
        if quantity > locked.quantity:
            raise ValidationError(f"موجودی کافی نیست. موجودی فعلی: {locked.quantity}")
        locked.quantity = locked.quantity - quantity
        locked.save(update_fields=["quantity", "updated_at"])
    elif kind == StockMovement.Kind.IN:
        locked.quantity = locked.quantity + quantity
        locked.save(update_fields=["quantity", "updated_at"])
    else:
        locked.quantity = quantity
        locked.save(update_fields=["quantity", "updated_at"])

    return StockMovement.objects.create(
        salon=salon,
        item=locked,
        kind=kind,
        quantity=quantity,
        note=note,
        appointment=appointment,
    )


def audit_inventory_consistency(*, salon=None) -> dict:
    """Read-only audit for negative stock and movement drift (informational)."""
    from django.db.models import Sum

    qs = InventoryItem.objects.all() if salon is None else InventoryItem.scoped(salon)
    negative = list(qs.filter(quantity__lt=0).values_list("pk", "name", "quantity"))
    drift = []
    for item in qs.iterator():
        ins = (
            StockMovement.objects.filter(item=item, kind=StockMovement.Kind.IN).aggregate(t=Sum("quantity"))["t"]
            or Decimal(0)
        )
        outs = (
            StockMovement.objects.filter(item=item, kind=StockMovement.Kind.OUT).aggregate(t=Sum("quantity"))["t"]
            or Decimal(0)
        )
        expected = ins - outs
        if item.quantity != expected:
            drift.append(
                {
                    "item_id": item.pk,
                    "stored": item.quantity,
                    "from_movements": expected,
                }
            )
    return {"negative_stock": negative, "quantity_drift": drift}