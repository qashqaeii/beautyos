import pytest
from django.urls import reverse

from apps.customers.models import Customer


@pytest.mark.django_db
def test_customer_list_view_toggle_preserves_search(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    Customer.objects.create(salon=salon, full_name="زهرا", phone="+989123456789")
    Customer.objects.create(salon=salon, full_name="مریم", phone="+989123456788")

    base = reverse("customers:list")
    response = client.get(f"{base}?q=زهرا&view=card")
    html = response.content.decode()
    assert "زهرا" in html
    assert "مریم" not in html

    response = client.get(f"{base}?q=زهرا&view=table")
    html = response.content.decode()
    assert "customers-list-table" in html
    assert "زهرا" in html
    assert "مریم" not in html


@pytest.mark.django_db
def test_customer_list_filter_empty_state(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    Customer.objects.create(salon=salon, full_name="علی", phone="+989111111111")
    response = client.get(reverse("customers:list"), {"q": "ناموجود"})
    assert response.status_code == 200
    assert "نتیجه‌ای یافت نشد" in response.content.decode()


@pytest.mark.django_db
def test_customer_list_uses_local_customer_network_hero_without_changing_create_flow(
    client, owner_membership, salon
):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    response = client.get(reverse("customers:list"))
    assert response.status_code == 200
    html = response.content.decode()
    assert 'customers-list-page__header customers-hero' in html
    assert "customers-network-hero.svg" in html
    assert "customers-hero.css" in html
    assert 'class="customers-hero__art" aria-hidden="true"' in html
    assert 'customers-list-page__add btn-primary' in html
    assert "customer-create-modal-title" in html


@pytest.mark.django_db
def test_customer_directory_compact_layout_preserves_pagination_and_filters(
    client, owner_membership, salon
):
    from django.contrib.staticfiles import finders
    from pathlib import Path

    for index in range(9):
        Customer.objects.create(
            salon=salon,
            full_name=f"مشتری جدید {index}",
            phone=f"+989128001{index:04d}",
        )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    response = client.get(reverse("customers:list"), {"view": "card"})
    assert response.status_code == 200
    html = response.content.decode()
    assert "customers-compact.css" in html
    assert 'role="region" aria-label="کارت‌های مشتریان"' in html
    assert "customers-network-hero.svg" in html
    assert "customer-create-modal-title" in html
    assert "customers-list-page__pagination" in html
    assert html.count('class="customers-list-card"') == 8

    second = client.get(reverse("customers:list"), {"view": "card", "page": "2"})
    assert second.status_code == 200
    assert second.content.decode().count('class="customers-list-card"') == 1
    filtered = client.get(reverse("customers:list"), {"view": "card", "q": "مشتری جدید 7"})
    assert filtered.status_code == 200
    assert 'مشتری جدید 7' in filtered.content.decode()
    assert filtered.content.decode().count('class="customers-list-card"') == 1
    css_path = finders.find("css/customers-compact.css")
    assert css_path is not None
    css = Path(css_path).read_text(encoding="utf-8")
    assert "height: 100dvh" not in css
    assert "overflow: hidden;" not in css
    assert "overflow: visible;" in css
    assert "@media (max-width: 639px)" in css


@pytest.mark.django_db
def test_customer_table_column_partitions_rtl_and_phone_isolation(client, owner_membership, salon):
    from pathlib import Path
    from django.contrib.staticfiles import finders

    customer = Customer.objects.create(
        salon=salon, full_name="مشتری ویژه با نام طولانی", phone="+989121234567"
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    response = client.get(reverse("customers:list"), {"view": "table"})
    assert response.status_code == 200
    body = response.content.decode()
    assert '<table class="customers-list-table" dir="rtl">' in body
    assert '<colgroup>' in body
    for col in ("name", "phone", "visits", "action"):
        assert f'customers-list-table__col--{col}' in body
    assert 'class="customers-list-table__action-head">عملیات</th>' in body
    assert 'class="customers-list-table__phone-value" dir="ltr"' in body
    assert "مشتری ویژه با نام طولانی" in body
    assert f'/customers/{customer.pk}/' in body

    css_path = finders.find("css/customers-compact.css")
    assert css_path is not None
    css = Path(css_path).read_text(encoding="utf-8")
    assert "table-layout: fixed" in css
    assert "justify-content: flex-start" in css
    assert "@media (max-width: 900px)" in css
