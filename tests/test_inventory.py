from decimal import Decimal

import pytest
from django.urls import reverse

from apps.inventory.models import InventoryCategory, InventoryItem, StockMovement
from apps.inventory.services import create_inventory_item
from apps.salons.models import SalonMembership


@pytest.mark.django_db
def test_create_inventory_item_with_initial_stock(client, owner_membership, salon):
    category = InventoryCategory.objects.create(salon=salon, name="مراقبت مو")
    item = create_inventory_item(
        salon=salon,
        name="شامپو",
        unit=InventoryItem.Unit.PIECE,
        minimum_quantity=Decimal("2"),
        category=category,
        initial_quantity=Decimal("8"),
    )
    item.refresh_from_db()
    assert item.quantity == Decimal("8")
    assert StockMovement.objects.filter(item=item, kind=StockMovement.Kind.IN).count() == 1


@pytest.mark.django_db
def test_inventory_list_filter_and_stock_flow(client, owner_membership, salon):
    cat = InventoryCategory.objects.create(salon=salon, name="لوازم مصرفی")
    a = create_inventory_item(
        salon=salon,
        name="پد پاک‌کننده",
        unit=InventoryItem.Unit.PACK,
        minimum_quantity=Decimal("1"),
        category=cat,
        initial_quantity=Decimal("5"),
    )
    create_inventory_item(
        salon=salon,
        name="بدون دسته",
        unit=InventoryItem.Unit.PIECE,
        minimum_quantity=Decimal("0"),
        category=None,
        initial_quantity=Decimal("3"),
    )

    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    url = reverse("inventory:list")
    res = client.get(url, {"category": str(cat.pk)})
    assert res.status_code == 200
    html = res.content.decode()
    assert "پد پاک‌کننده" in html
    assert 'inventory-table__name">بدون دسته<' not in html
    assert 'inventory-card__name">بدون دسته<' not in html

    res_none = client.get(url, {"category": "none"})
    assert "بدون دسته" in res_none.content.decode()

    stock_in_url = reverse("inventory:stock_in", kwargs={"pk": a.pk})
    client.post(stock_in_url, {"quantity": "2", "note": ""})
    a.refresh_from_db()
    assert a.quantity == Decimal("7")

    stock_out_url = reverse("inventory:stock_out", kwargs={"pk": a.pk})
    client.post(stock_out_url, {"quantity": "1", "note": ""})
    a.refresh_from_db()
    assert a.quantity == Decimal("6")


@pytest.mark.django_db
def test_item_create_product_name_field_and_save(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    url = reverse("inventory:create")
    get_res = client.get(url, follow=True)
    html = get_res.content.decode()
    assert get_res.request["PATH_INFO"] == reverse("inventory:list")
    assert 'name="inventory_product_name"' in html
    assert "autocomplete" in html

    post = client.post(
        url,
        {
            "intent": "save_item",
            "inventory_product_name": "پودر دکلره",
            "unit": InventoryItem.Unit.PIECE,
            "initial_quantity": "1",
            "minimum_quantity": "0",
        },
    )
    assert post.status_code == 302
    assert InventoryItem.scoped(salon).filter(name="پودر دکلره").exists()


@pytest.mark.django_db
def test_inventory_permissions_blocked_for_receptionist(client, salon):
    from apps.accounts.models import User

    reception_user = User.objects.create_user(phone="+989129876543", full_name="پذیرش")
    reception = SalonMembership.objects.create(
        user=reception_user,
        salon=salon,
        role=SalonMembership.Role.RECEPTIONIST,
    )
    client.force_login(reception.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    res = client.get(reverse("inventory:list"))
    assert res.status_code == 403
