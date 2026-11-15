import pytest
from django.urls import reverse

from apps.services.models import Service


@pytest.mark.django_db
def test_service_edit_get_redirects_to_list_modal(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    service = Service.objects.create(salon=salon, name="رنگ مو", price_toman=500_000, duration_minutes=60)
    url = reverse("services:edit", kwargs={"pk": service.pk})
    response = client.get(url)
    assert response.status_code == 302
    assert f"edit={service.pk}" in response.url


@pytest.mark.django_db
def test_service_list_edit_query_opens_modal(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    service = Service.objects.create(salon=salon, name="مانیکور", price_toman=200_000, duration_minutes=45)
    url = reverse("services:list")
    response = client.get(f"{url}?edit={service.pk}")
    assert response.status_code == 200
    html = response.content.decode()
    assert "service-edit-form" in html
    assert "ویرایش خدمت" in html
    assert "editOpen: true" in html


@pytest.mark.django_db
def test_service_edit_post_success(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    service = Service.objects.create(salon=salon, name="پدیکور", price_toman=180_000, duration_minutes=40)
    url = reverse("services:edit", kwargs={"pk": service.pk})
    response = client.post(
        url,
        {
            "intent": "save_service",
            "name": "پدیکور VIP",
            "price_toman": "220000",
            "duration_minutes": "50",
            "sort_order": "0",
            "description": "",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    service.refresh_from_db()
    assert service.name == "پدیکور VIP"
    assert service.price_toman == 220_000
